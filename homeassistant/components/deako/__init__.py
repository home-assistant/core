"""The deako integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import socket
import time

from pydeako import (
    Deako,
    DeakoConnectionPool,
    DeakoDiscoverer,
    FindDevicesError,
    tcp_probe,
)
from zeroconf import Zeroconf as Zeroconf_

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_KNOWN_BRIDGES,
    CONF_SECONDARY_HOST,
    DEAKO_DEFAULT_PORT,
    DOMAIN,
    NAME,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]
DEAKO_MDNS_TYPE = "_deako._tcp.local."

# How often to scan for a failover bridge candidate via zeroconf
FAILOVER_SCAN_INTERVAL_S = 60
# How often to retry a pending primary/failover bridge
PENDING_RETRY_INTERVAL_S = 30
# Max hours to retry a pending bridge before giving up
PENDING_MAX_HOURS = 48


@dataclass
class DeakoRuntimeData:
    """Runtime data for the Deako integration."""

    hass: HomeAssistant
    entry_id: str
    pool: DeakoConnectionPool
    active_zc_info: dict[str, str] = field(default_factory=dict)
    failover_zc_info: dict[str, str] = field(default_factory=dict)
    pending_primary_host: str | None = None
    _pending_primary_since: float = 0.0
    _failover_scan_task: asyncio.Task | None = None
    _pending_retry_task: asyncio.Task | None = None
    _stopped: bool = False

    @property
    def active_host(self) -> str | None:
        """Return the active bridge IP."""
        return self.pool.active_host

    @property
    def failover_host(self) -> str | None:
        """Return the failover bridge IP."""
        return self.pool.failover_host

    @property
    def connection(self) -> Deako | None:
        """Return the underlying Deako connection (for device queries)."""
        return self.pool.connection

    async def start_background_tasks(self) -> None:
        """Start the failover scanner and pending retry tasks."""
        self._failover_scan_task = asyncio.create_task(
            self._failover_scan_loop()
        )
        if self.pending_primary_host:
            self._pending_retry_task = asyncio.create_task(
                self._pending_retry_loop()
            )

    async def _failover_scan_loop(self) -> None:
        """Periodically scan for a second Deako bridge to use as failover."""
        await asyncio.sleep(10)  # let startup settle
        while not self._stopped:
            pool_state = self.pool.state

            # Skip if we already have a healthy failover
            if pool_state.failover_host and pool_state.is_failover_alive:
                await asyncio.sleep(FAILOVER_SCAN_INTERVAL_S)
                continue

            # Don't scan while a switch is in progress
            if pool_state.is_switching:
                await asyncio.sleep(5)
                continue

            _LOGGER.debug(
                "Failover scanner: scanning (active=%s)",
                pool_state.active_host,
            )

            try:
                _zc = await zeroconf.async_get_instance(self.hass)
                bridges = await self.hass.async_add_executor_job(
                    _find_all_bridges_zeroconf, _zc
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Failover scanner: mDNS browse failed")
                await asyncio.sleep(FAILOVER_SCAN_INTERVAL_S)
                continue

            _LOGGER.debug(
                "Failover scanner: found %d candidates: %s",
                len(bridges), list(bridges.keys()),
            )

            # Find a bridge that isn't the active primary
            for ip, info in bridges.items():
                if ip == pool_state.active_host:
                    continue
                if not await tcp_probe(ip):
                    continue
                # Re-check after probe
                if ip == self.pool.active_host:
                    continue

                _LOGGER.debug(
                    "Failover scanner: %s passed probe, setting as failover", ip
                )
                if await self.pool.set_failover_host(ip):
                    self.failover_zc_info = dict(info)
                    serial = info.get("serial", "unknown")
                    _LOGGER.info(
                        "Failover bridge ESTABLISHED: %s (SN: %s)", ip, serial
                    )
                    # Update device registry and known bridges
                    try:
                        entry = self.hass.config_entries.async_get_entry(
                            self.entry_id
                        )
                        if entry:
                            _store_known_bridge(self.hass, entry, ip, info)
                            _update_bridge_device(
                                self.hass, entry,
                                self.pool.active_host,
                                self.active_zc_info,
                                failover_host=ip,
                                failover_zc_info=info,
                            )
                    except Exception:  # noqa: BLE001
                        _LOGGER.debug("Error updating device registry")
                    break

            await asyncio.sleep(FAILOVER_SCAN_INTERVAL_S)

    async def _pending_retry_loop(self) -> None:
        """Retry connecting to a pending primary bridge until it comes online."""
        await asyncio.sleep(15)  # let startup settle
        while not self._stopped and self.pending_primary_host:
            await asyncio.sleep(PENDING_RETRY_INTERVAL_S)

            if not self.pending_primary_host:
                break
            if self.pending_primary_host == self.pool.active_host:
                self.pending_primary_host = None
                break

            elapsed_h = (time.monotonic() - self._pending_primary_since) / 3600
            if elapsed_h > PENDING_MAX_HOURS:
                _LOGGER.error(
                    "Pending primary %s did not come online within %dh",
                    self.pending_primary_host, PENDING_MAX_HOURS,
                )
                self.pending_primary_host = None
                break

            _LOGGER.debug(
                "Pending primary retry: probing %s (%.1fh elapsed)",
                self.pending_primary_host, elapsed_h,
            )

            if await tcp_probe(self.pending_primary_host, timeout=5.0):
                _LOGGER.info(
                    "Pending primary %s is online! Switching...",
                    self.pending_primary_host,
                )
                await self._switch_to_pending_primary()

    async def _switch_to_pending_primary(self) -> None:
        """Switch to the pending primary by recreating the pool."""
        if not self.pending_primary_host:
            return

        target = self.pending_primary_host
        old_host = self.pool.active_host

        # Stop the old pool
        await self.pool.stop()

        # Create a new pool with the pending primary
        new_pool = DeakoConnectionPool(
            primary_host=target,
            failover_host=old_host if old_host != target else None,
            client_name=NAME,
            on_failover_switch=self._on_failover_switch,
            on_connection_lost=self._on_connection_lost,
        )

        if await new_pool.start():
            # Transfer state callbacks from old devices
            old_conn = self.pool.connection
            if old_conn and new_pool.connection:
                old_devices = old_conn.get_devices()
                for uuid_key in old_devices:
                    if "callback" in old_devices[uuid_key]:
                        new_pool.set_state_callback(
                            uuid_key, old_devices[uuid_key]["callback"]
                        )

            self.pool = new_pool
            self.pending_primary_host = None

            # Look up zc info for new primary
            try:
                _zc = await zeroconf.async_get_instance(self.hass)
                fresh = await self.hass.async_add_executor_job(
                    _lookup_bridge_zeroconf, _zc, target
                )
                if fresh:
                    self.active_zc_info = fresh
            except Exception:  # noqa: BLE001
                pass

            _LOGGER.info("Switched to pending primary %s", target)

            # Update device registry
            try:
                entry = self.hass.config_entries.async_get_entry(self.entry_id)
                if entry:
                    _store_known_bridge(
                        self.hass, entry, target, self.active_zc_info
                    )
                    _update_bridge_device(
                        self.hass, entry, target, self.active_zc_info,
                        failover_host=self.pool.failover_host,
                        failover_zc_info=self.failover_zc_info
                        if self.pool.failover_host else None,
                    )
            except Exception:  # noqa: BLE001
                pass
        else:
            _LOGGER.warning(
                "Could not connect to pending primary %s, staying on current",
                target,
            )
            # Restart the old pool
            await self.pool.start()

    def _on_failover_switch(
        self, new_active: str, new_failover: str | None
    ) -> None:
        """Handle pool failover switch — update HA device registry."""
        _LOGGER.info(
            "Pool failover switch: active=%s, failover=%s",
            new_active, new_failover,
        )
        # Swap zc_info
        old_active_zc = dict(self.active_zc_info)
        self.active_zc_info = dict(self.failover_zc_info) if self.failover_zc_info else {}
        if new_failover:
            self.failover_zc_info = old_active_zc
        else:
            self.failover_zc_info = {}

        try:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                _update_bridge_device(
                    self.hass, entry, new_active, self.active_zc_info,
                    failover_host=new_failover,
                    failover_zc_info=self.failover_zc_info
                    if new_failover else None,
                )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error updating device registry after failover")

    def _on_connection_lost(self) -> None:
        """Handle pool connection lost with no failover available."""
        _LOGGER.warning(
            "Connection to bridge lost and no failover available"
        )

    def stop(self) -> None:
        """Stop all background tasks."""
        self._stopped = True
        if self._failover_scan_task is not None:
            self._failover_scan_task.cancel()
            self._failover_scan_task = None
        if self._pending_retry_task is not None:
            self._pending_retry_task.cancel()
            self._pending_retry_task = None


type DeakoConfigEntry = ConfigEntry[DeakoRuntimeData]


def _lookup_bridge_zeroconf(
    zc: Zeroconf_, host: str | None = None
) -> dict[str, str]:
    """Look up zeroconf TXT record info for a Deako bridge."""
    import time as _time  # noqa: PLC0415

    from zeroconf import ServiceBrowser as _SB  # noqa: PLC0415
    from zeroconf import ServiceInfo, ServiceListener as _SL  # noqa: PLC0415

    class _Collector(_SL):
        def __init__(self):
            self.names: list[tuple[str, str]] = []

        def add_service(self, zc, type_, name):
            self.names.append((type_, name))

        def remove_service(self, zc, type_, name):
            pass

        def update_service(self, zc, type_, name):
            self.names.append((type_, name))

    collector = _Collector()
    browser = _SB(zc, DEAKO_MDNS_TYPE, collector)

    deadline = _time.monotonic() + 2.0
    while _time.monotonic() < deadline:
        _time.sleep(0.3)
        if collector.names:
            _time.sleep(0.5)
            break

    browser.cancel()

    seen: set[str] = set()
    for type_, name in collector.names:
        if name in seen:
            continue
        seen.add(name)
        try:
            info = ServiceInfo(type_, name)
            if info.request(zc, timeout=2000):
                for addr_bytes in info.addresses:
                    ip = socket.inet_ntoa(addr_bytes)
                    if host is not None and ip != host:
                        continue
                    props = info.properties or {}
                    return {
                        "ip": ip,
                        "serial": props.get(b"sn", b"").decode(
                            "utf-8", errors="replace"
                        ),
                        "version": props.get(b"version", b"").decode(
                            "utf-8", errors="replace"
                        ),
                    }
        except Exception:  # noqa: BLE001
            continue
    return {}


def _find_all_bridges_zeroconf(zc: Zeroconf_) -> dict[str, dict[str, str]]:
    """Find all Deako bridges via active mDNS browse."""
    import time as _time  # noqa: PLC0415

    from zeroconf import ServiceBrowser as _SB  # noqa: PLC0415
    from zeroconf import ServiceInfo, ServiceListener as _SL  # noqa: PLC0415

    class _Collector(_SL):
        def __init__(self):
            self.names: list[tuple[str, str]] = []

        def add_service(self, zc, type_, name):
            self.names.append((type_, name))

        def remove_service(self, zc, type_, name):
            pass

        def update_service(self, zc, type_, name):
            self.names.append((type_, name))

    collector = _Collector()
    browser = _SB(zc, DEAKO_MDNS_TYPE, collector)

    deadline = _time.monotonic() + 5.0
    while _time.monotonic() < deadline:
        _time.sleep(0.5)
        if collector.names:
            _time.sleep(2.0)
            break

    browser.cancel()

    bridges: dict[str, dict[str, str]] = {}
    seen_names: set[str] = set()
    for type_, name in collector.names:
        if name in seen_names:
            continue
        seen_names.add(name)
        try:
            info = ServiceInfo(type_, name)
            if info.request(zc, timeout=2000):
                for addr_bytes in info.addresses:
                    ip = socket.inet_ntoa(addr_bytes)
                    props = info.properties or {}
                    bridges[ip] = {
                        "serial": props.get(b"sn", b"").decode(
                            "utf-8", errors="replace"
                        ),
                        "version": props.get(b"version", b"").decode(
                            "utf-8", errors="replace"
                        ),
                    }
        except Exception:  # noqa: BLE001
            continue
    return bridges


def _update_bridge_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    active_host: str | None,
    active_zc_info: dict[str, str],
    failover_host: str | None = None,
    failover_zc_info: dict[str, str] | None = None,
) -> None:
    """Create or update bridge devices in HA's device registry."""
    device_reg = dr.async_get(hass)

    # --- Primary bridge device ---
    bridge_serial = active_zc_info.get("serial", "")
    bridge_fw = active_zc_info.get("version", "")
    bridge_name = f"{NAME} Bridge (Primary)"
    identifiers: set[tuple[str, str]] = {(DOMAIN, entry.entry_id)}

    primary_info: dict = {
        "config_entry_id": entry.entry_id,
        "identifiers": identifiers,
        "manufacturer": "Deako",
        "name": bridge_name,
        "model": "Bridge",
        "hw_version": "Role: Primary",
    }
    if active_host and active_host != "discovered":
        primary_info["configuration_url"] = f"http://{active_host}"
        primary_info["hw_version"] = f"Role: Primary  |  IP: {active_host}"
    if bridge_serial:
        primary_info["serial_number"] = bridge_serial
    if bridge_fw:
        primary_info["sw_version"] = bridge_fw

    primary_device = device_reg.async_get_or_create(**primary_info)
    update_kwargs: dict = {}
    if primary_device.identifiers != identifiers:
        update_kwargs["new_identifiers"] = identifiers
    if primary_device.serial_number != (bridge_serial or None):
        update_kwargs["serial_number"] = bridge_serial or None
    if primary_device.sw_version != (bridge_fw or None):
        update_kwargs["sw_version"] = bridge_fw or None
    if update_kwargs:
        device_reg.async_update_device(primary_device.id, **update_kwargs)

    # --- Failover bridge device ---
    if failover_host:
        fo_zc = failover_zc_info or {}
        if not fo_zc.get("serial"):
            known = entry.data.get(CONF_KNOWN_BRIDGES, {})
            if failover_host in known:
                fo_zc = {**fo_zc, **known[failover_host]}

        fo_serial = fo_zc.get("serial", "")
        fo_fw = fo_zc.get("version", "")
        fo_name = f"{NAME} Bridge (Failover)"
        fo_identifiers: set[tuple[str, str]] = {
            (DOMAIN, f"{entry.entry_id}_failover")
        }

        fo_info: dict = {
            "config_entry_id": entry.entry_id,
            "identifiers": fo_identifiers,
            "manufacturer": "Deako",
            "name": fo_name,
            "model": "Bridge",
            "hw_version": f"Role: Failover  |  IP: {failover_host}",
            "configuration_url": f"http://{failover_host}",
        }
        if fo_serial:
            fo_info["serial_number"] = fo_serial
        if fo_fw:
            fo_info["sw_version"] = fo_fw

        fo_device = device_reg.async_get_or_create(**fo_info)
        update_kwargs = {}
        if fo_device.identifiers != fo_identifiers:
            update_kwargs["new_identifiers"] = fo_identifiers
        if fo_device.serial_number != (fo_serial or None):
            update_kwargs["serial_number"] = fo_serial or None
        if fo_device.sw_version != (fo_fw or None):
            update_kwargs["sw_version"] = fo_fw or None
        if update_kwargs:
            device_reg.async_update_device(fo_device.id, **update_kwargs)
    else:
        # No failover — remove stale failover card
        fo_id = (DOMAIN, f"{entry.entry_id}_failover")
        for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
            if fo_id in device.identifiers:
                device_reg.async_remove_device(device.id)
                break


def _store_known_bridge(
    hass: HomeAssistant,
    entry: ConfigEntry,
    host: str | None,
    zc_info: dict[str, str],
) -> None:
    """Store a bridge in known_bridges dict in config entry data."""
    if not host or host == "discovered":
        return
    known: dict[str, dict[str, str]] = dict(entry.data.get(CONF_KNOWN_BRIDGES, {}))
    known[host] = {
        "serial": zc_info.get("serial", ""),
        "version": zc_info.get("version", ""),
    }
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_KNOWN_BRIDGES: known},
    )


async def async_setup_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> bool:
    """Set up deako."""
    primary_host = entry.data.get(CONF_HOST)
    secondary_host = entry.data.get(CONF_SECONDARY_HOST)

    # If no primary host configured, discover one via zeroconf
    if not primary_host:
        _zc = await zeroconf.async_get_instance(hass)
        discoverer = DeakoDiscoverer(_zc)
        # Use a temporary Deako to discover the bridge IP
        temp_conn = Deako(discoverer.get_address)
        try:
            await temp_conn.connect()
            await temp_conn.find_devices()
        except FindDevicesError as exc:
            await temp_conn.disconnect()
            raise ConfigEntryNotReady(exc) from exc

        devices = temp_conn.get_devices()
        if len(devices) == 0:
            await temp_conn.disconnect()
            raise ConfigEntryNotReady("No devices found")

        # Extract the actual IP from the connection
        try:
            conn_address = temp_conn.connection_manager.connection.address
            primary_host = conn_address.split(":")[0]
        except (AttributeError, IndexError):
            _LOGGER.warning("Could not determine connected bridge IP")
            await temp_conn.disconnect()
            raise ConfigEntryNotReady("Could not determine bridge IP")

        await temp_conn.disconnect()
        # Give bridge time to release the connection
        await asyncio.sleep(2)

    # Create runtime data placeholder for callbacks
    runtime_data = DeakoRuntimeData(
        hass=hass,
        entry_id=entry.entry_id,
        pool=None,  # type: ignore[arg-type] — set below
    )

    # Create the connection pool
    pool = DeakoConnectionPool(
        primary_host=primary_host,
        failover_host=secondary_host if secondary_host != primary_host else None,
        client_name=NAME,
        on_failover_switch=runtime_data._on_failover_switch,
        on_connection_lost=runtime_data._on_connection_lost,
    )

    # Give the bridge time to release any previous TCP session.
    # Deako bridges only accept one connection at a time and need
    # several seconds to recycle after a disconnect (e.g. during
    # reload or reconfigure).
    if primary_host:
        await asyncio.sleep(5)

    if not await pool.start():
        raise ConfigEntryNotReady(
            f"Could not connect to Deako bridge at {primary_host}"
        )

    runtime_data.pool = pool

    # Look up zeroconf info for the active bridge
    zc_info: dict[str, str] = {}
    try:
        _zc = await zeroconf.async_get_instance(hass)
        zc_info = await hass.async_add_executor_job(
            _lookup_bridge_zeroconf, _zc, pool.active_host
        )
    except Exception:  # noqa: BLE001
        pass

    # Fall back to known_bridges
    if not zc_info.get("serial"):
        known = entry.data.get(CONF_KNOWN_BRIDGES, {})
        if pool.active_host and pool.active_host in known:
            stored = known[pool.active_host]
            if stored.get("serial"):
                zc_info.setdefault("serial", stored["serial"])
            if stored.get("version"):
                zc_info.setdefault("version", stored["version"])

    runtime_data.active_zc_info = dict(zc_info) if zc_info else {}

    # Detect pending primary (configured but offline, fell back to another)
    if (
        entry.data.get(CONF_HOST)
        and pool.active_host != entry.data.get(CONF_HOST)
    ):
        runtime_data.pending_primary_host = entry.data[CONF_HOST]
        runtime_data._pending_primary_since = time.monotonic()
        _LOGGER.warning(
            "Configured primary %s is offline. Running on %s. "
            "Will retry in background.",
            entry.data[CONF_HOST], pool.active_host,
        )

    # Register bridge device
    _update_bridge_device(
        hass, entry, pool.active_host, zc_info,
        failover_host=pool.failover_host,
    )

    _LOGGER.info("Deako bridge active on: %s", pool.active_host)
    _store_known_bridge(hass, entry, pool.active_host, zc_info)

    entry.runtime_data = runtime_data

    # Start background tasks
    await runtime_data.start_background_tasks()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove stale devices
    device_reg = dr.async_get(hass)
    current_uuids = set(pool.get_devices().keys())
    keep_ids = {(DOMAIN, uuid) for uuid in current_uuids}
    keep_ids.add((DOMAIN, entry.entry_id))
    if pool.failover_host:
        keep_ids.add((DOMAIN, f"{entry.entry_id}_failover"))

    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        dominated = {id_pair for id_pair in device.identifiers if id_pair[0] == DOMAIN}
        if dominated and not dominated & keep_ids:
            _LOGGER.info(
                "Removing stale device %s (%s)", device.name, dominated
            )
            device_reg.async_remove_device(device.id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.stop()
    await entry.runtime_data.pool.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
