"""The deako integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import socket
import time

from pydeako import Deako, DeakoDiscoverer, FindDevicesError
from zeroconf import Zeroconf as Zeroconf_

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    COMMAND_THROTTLE_S,
    CONF_KNOWN_BRIDGES,
    CONF_SECONDARY_HOST,
    DEAKO_DEFAULT_PORT,
    DOMAIN,
    NAME,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]
DEAKO_MDNS_TYPE = "_deako._tcp.local."

# How often to check if the failover keepalive socket is still alive
FAILOVER_KEEPALIVE_CHECK_S = 30
# How often to scan for a failover bridge candidate via zeroconf
FAILOVER_SCAN_INTERVAL_S = 60



def _lookup_bridge_zeroconf(
    zc: Zeroconf_, host: str | None = None
) -> dict[str, str]:
    """Look up zeroconf TXT record info for a Deako bridge.

    Uses an active ServiceBrowser to query the network (not just the
    cache, which may be empty at startup). Waits up to 5 seconds.

    If host is provided, returns info for that specific IP.
    If host is None, returns info for the first Deako bridge found.
    Returns dict with 'serial', 'version', and 'ip' if found, empty dict otherwise.
    """
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


class _FailoverKeepAlive:
    """Holds a raw TCP socket open to a failover bridge to keep it awake.

    Deako devices stay in bridge mode (persistent WiFi) as long as
    a TCP connection is held open on port 23. This class maintains
    that connection and monitors it in the background.
    """

    def __init__(self, host: str, port: int = DEAKO_DEFAULT_PORT) -> None:
        """Initialize with failover bridge address."""
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._monitor_task: asyncio.Task | None = None
        self._stopped = False

    async def start(self, loop: asyncio.AbstractEventLoop) -> bool:
        """Open the keepalive socket. Returns True if successful."""
        try:
            self._socket = await loop.run_in_executor(
                None, self._connect_sync
            )
            _LOGGER.info(
                "Failover keepalive connected to %s:%s", self.host, self.port
            )
            self._monitor_task = asyncio.create_task(self._monitor())
            return True
        except OSError as exc:
            _LOGGER.debug(
                "Could not connect keepalive to %s:%s: %s",
                self.host,
                self.port,
                exc,
            )
            return False

    def _connect_sync(self) -> socket.socket:
        """Synchronous socket connect (run in executor)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((self.host, self.port))
        sock.settimeout(None)  # restore blocking mode with no timeout
        return sock

    async def _monitor(self) -> None:
        """Monitor the keepalive socket and log if it drops."""
        loop = asyncio.get_event_loop()
        while not self._stopped:
            await asyncio.sleep(FAILOVER_KEEPALIVE_CHECK_S)
            if self._socket is None:
                break
            try:
                # Non-blocking check: try to recv without blocking.
                # If the remote closed, recv returns b''.
                data = await loop.run_in_executor(
                    None, self._check_socket
                )
                if data is False:
                    _LOGGER.warning(
                        "Failover keepalive to %s dropped", self.host
                    )
                    self._socket = None
                    break
            except Exception:  # noqa: BLE001
                _LOGGER.warning(
                    "Failover keepalive to %s error", self.host
                )
                self._socket = None
                break

    def _check_socket(self) -> bool:
        """Check if socket is still alive. Returns False if dead."""
        if self._socket is None:
            return False
        try:
            self._socket.setblocking(False)
            try:
                data = self._socket.recv(1)
                if data == b"":
                    return False  # remote closed
            except BlockingIOError:
                pass  # no data available, socket still alive
            finally:
                self._socket.setblocking(True)
            return True
        except OSError:
            return False

    @property
    def is_alive(self) -> bool:
        """Return True if the keepalive socket is still connected."""
        return self._socket is not None and not self._stopped

    def close(self) -> None:
        """Close the keepalive socket and stop monitoring."""
        self._stopped = True
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None


@dataclass
class DeakoRuntimeData:
    """Runtime data for the Deako integration."""

    hass: HomeAssistant
    entry_id: str
    connection: Deako
    active_host: str | None
    active_zc_info: dict[str, str] = field(default_factory=dict)
    failover_host: str | None = None
    failover_zc_info: dict[str, str] = field(default_factory=dict)
    failover_keepalive: _FailoverKeepAlive | None = None
    pending_primary_host: str | None = None
    _pending_primary_since: float = 0.0
    pending_failover_host: str | None = None
    _pending_failover_since: float = 0.0
    _command_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _last_command_time: float = 0.0
    _consecutive_failures: int = 0
    _failover_scan_task: asyncio.Task | None = None
    _health_monitor_task: asyncio.Task | None = None
    _stopped: bool = False
    _switching: bool = False

    async def throttled_control(
        self, uuid: str, power: bool, dim: int | None = None
    ) -> None:
        """Send a control command with global 250ms throttle.

        The background health monitor proactively switches to the
        failover bridge when it detects the primary is dead, so most
        commands should just succeed. If a command arrives during the
        brief switch window, we wait and retry on the new connection.
        """
        async with self._command_lock:
            now = time.monotonic()
            elapsed = now - self._last_command_time
            if elapsed < COMMAND_THROTTLE_S:
                await asyncio.sleep(COMMAND_THROTTLE_S - elapsed)

            # If a failover switch is in progress, wait for it
            if self._switching:
                _LOGGER.debug("Failover switch in progress, waiting...")
                for _ in range(20):  # wait up to 10 seconds
                    await asyncio.sleep(0.5)
                    if not self._switching:
                        break

            # Check if the connection is alive before sending
            mgr = self.connection.connection_manager
            if mgr.connection is not None:
                _LOGGER.debug(
                    "Control: %s → power=%s dim=%s (via %s)",
                    uuid, power, dim, self.active_host,
                )
                await self.connection.control_device(uuid, power, dim)
                self._last_command_time = time.monotonic()
                self._consecutive_failures = 0
                return

            # Connection is dead — try immediate inline failover
            # (health monitor may not have caught it yet)
            self._consecutive_failures += 1
            _LOGGER.warning(
                "Control command failed, connection dead (attempt %d)",
                self._consecutive_failures,
            )

            if (
                self.failover_host
                and self.failover_keepalive
                and self.failover_keepalive.is_alive
            ):
                await self._switch_to_failover()
                # Retry the command on the new connection
                try:
                    await self.connection.control_device(uuid, power, dim)
                except Exception:
                    _LOGGER.warning(
                        "Control command failed after switching to failover bridge at %s",
                        self.active_host,
                    )
                    raise
                else:
                    self._consecutive_failures = 0
                finally:
                    self._last_command_time = time.monotonic()
                return
            self._last_command_time = time.monotonic()

    async def _switch_to_failover(self) -> None:
        """Switch the active connection to the failover bridge."""
        if not self.failover_host:
            return
        if self._switching:
            return  # already in progress

        self._switching = True
        _LOGGER.warning(
            "Switching to failover bridge at %s", self.failover_host
        )

        # Close the old primary connection
        try:
            await self.connection.disconnect()
        except Exception:  # noqa: BLE001
            pass

        # Close the keepalive socket — we're about to open a real
        # pydeako connection to this host instead
        if self.failover_keepalive:
            self.failover_keepalive.close()
            self.failover_keepalive = None

        # Give the bridge time to release the keepalive session and
        # be ready for a new full pydeako connection.  Deako bridges
        # (especially older gen) need several seconds to recycle.
        await asyncio.sleep(5)

        # Connect to the failover bridge as the new primary
        host = self.failover_host
        self.failover_host = None

        async def get_address():
            return f"{host}:{DEAKO_DEFAULT_PORT}", NAME

        new_connection = Deako(get_address)
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    _LOGGER.info(
                        "Retrying failover connection to %s (attempt %d/3)",
                        host, attempt + 1,
                    )
                    await asyncio.sleep(3)
                    new_connection = Deako(get_address)
                await new_connection.connect()
                await new_connection.find_devices()
                last_exc = None
                break
            except (FindDevicesError, OSError) as exc:
                last_exc = exc
                _LOGGER.warning(
                    "Failover connect attempt %d/3 to %s failed: %s",
                    attempt + 1, host, exc,
                )
                try:
                    await new_connection.disconnect()
                except Exception:  # noqa: BLE001
                    pass

        if last_exc is not None:
            _LOGGER.error("All failover attempts to %s failed", host)
            self._switching = False
            return

        # Transfer state callbacks from old devices to new connection
        old_devices = self.connection.get_devices()
        for uuid_key in old_devices:
            if "callback" in old_devices[uuid_key]:
                new_connection.set_state_callback(
                    uuid_key, old_devices[uuid_key]["callback"]
                )

        self.connection = new_connection
        self.active_host = host
        # The failover's zc_info becomes the active zc_info
        self.active_zc_info = dict(self.failover_zc_info) if self.failover_zc_info else {}
        self.failover_zc_info = {}
        _LOGGER.info("Successfully failed over to bridge at %s", host)

        # Update the bridge device in HA's device registry
        try:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                _update_bridge_device(
                    self.hass,
                    entry,
                    self.active_host,
                    self.active_zc_info,
                    failover_host=None,  # no failover yet, scanner will find one
                    failover_zc_info=None,
                )
                # Also look up fresh zc_info if we don't have it
                if not self.active_zc_info.get("serial"):
                    try:
                        _zc = await zeroconf.async_get_instance(self.hass)
                        fresh_info = await self.hass.async_add_executor_job(
                            _lookup_bridge_zeroconf, _zc, host
                        )
                        if fresh_info:
                            self.active_zc_info = fresh_info
                            _update_bridge_device(
                                self.hass, entry, self.active_host,
                                self.active_zc_info,
                            )
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not update device registry after failover")
        finally:
            self._switching = False

    async def _switch_to_pending_primary(self) -> None:
        """Voluntarily switch to the pending primary bridge.

        The pending primary has come online after being offline when the
        user configured it.  We connect to it, and the old active bridge
        becomes the new failover candidate.
        """
        if not self.pending_primary_host:
            return
        if self._switching:
            return

        self._switching = True
        target = self.pending_primary_host
        _LOGGER.info("Voluntary switch to pending primary %s", target)

        # Close existing failover keepalive if any
        if self.failover_keepalive:
            self.failover_keepalive.close()
            self.failover_keepalive = None

        # Remember old active bridge so we can make it the failover
        old_host = self.active_host

        # Disconnect from current bridge
        try:
            await self.connection.disconnect()
        except Exception:  # noqa: BLE001
            pass

        await asyncio.sleep(2)

        # Connect to the pending primary
        async def get_address():
            return f"{target}:{DEAKO_DEFAULT_PORT}", NAME

        new_connection = Deako(get_address)
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    _LOGGER.info(
                        "Retrying pending primary %s (attempt %d/3)",
                        target, attempt + 1,
                    )
                    await asyncio.sleep(3)
                    new_connection = Deako(get_address)
                await new_connection.connect()
                await new_connection.find_devices()
                last_exc = None
                break
            except (FindDevicesError, OSError) as exc:
                last_exc = exc
                _LOGGER.warning(
                    "Pending primary connect attempt %d/3 to %s failed: %s",
                    attempt + 1, target, exc,
                )
                try:
                    await new_connection.disconnect()
                except Exception:  # noqa: BLE001
                    pass

        if last_exc is not None:
            _LOGGER.error(
                "Could not connect to pending primary %s, "
                "staying on current bridge",
                target,
            )
            # Reconnect to old bridge
            try:
                async def get_old_address():
                    return f"{old_host}:{DEAKO_DEFAULT_PORT}", NAME

                old_conn = Deako(get_old_address)
                await old_conn.connect()
                await old_conn.find_devices()
                # Transfer callbacks
                old_devices = self.connection.get_devices()
                for uuid_key in old_devices:
                    if "callback" in old_devices[uuid_key]:
                        old_conn.set_state_callback(
                            uuid_key, old_devices[uuid_key]["callback"]
                        )
                self.connection = old_conn
            except Exception:  # noqa: BLE001
                _LOGGER.error("Failed to reconnect to old bridge %s", old_host)
            self._switching = False
            return

        # Transfer state callbacks
        old_devices = self.connection.get_devices()
        for uuid_key in old_devices:
            if "callback" in old_devices[uuid_key]:
                new_connection.set_state_callback(
                    uuid_key, old_devices[uuid_key]["callback"]
                )

        self.connection = new_connection
        self.active_host = target
        self.pending_primary_host = None  # fulfilled

        # Look up zeroconf info for the new primary
        try:
            _zc = await zeroconf.async_get_instance(self.hass)
            fresh = await self.hass.async_add_executor_job(
                _lookup_bridge_zeroconf, _zc, target
            )
            if fresh:
                self.active_zc_info = fresh
        except Exception:  # noqa: BLE001
            pass

        _LOGGER.info(
            "Successfully switched to pending primary %s", target
        )

        # The old active bridge becomes a failover candidate.
        # Open a keepalive to it so it stays awake.
        if old_host and old_host != target and old_host != "discovered":
            self.failover_host = old_host
            keepalive = _FailoverKeepAlive(old_host)
            loop = asyncio.get_event_loop()
            if await keepalive.start(loop):
                self.failover_keepalive = keepalive
                # Look up zc info for old bridge (now failover)
                try:
                    _zc = await zeroconf.async_get_instance(self.hass)
                    fo_info = await self.hass.async_add_executor_job(
                        _lookup_bridge_zeroconf, _zc, old_host
                    )
                    if fo_info:
                        self.failover_zc_info = fo_info
                except Exception:  # noqa: BLE001
                    pass
                _LOGGER.info(
                    "Old primary %s is now failover", old_host
                )
            else:
                self.failover_host = None
                keepalive.close()

        # Update device registry
        try:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                _store_known_bridge(self.hass, entry, target, self.active_zc_info)
                _update_bridge_device(
                    self.hass, entry, self.active_host, self.active_zc_info,
                    failover_host=self.failover_host,
                    failover_zc_info=self.failover_zc_info
                    if self.failover_host else None,
                )
        except Exception:  # noqa: BLE001
            pass

        # Send notification that the switch succeeded
        try:
            from homeassistant.components.persistent_notification import async_create  # noqa: PLC0415

            async_create(
                self.hass,
                f"The Deako integration has successfully switched to the "
                f"bridge at {target}. The previous bridge ({old_host}) "
                f"is now the failover.",
                "Deako Bridge Changed",
                f"{DOMAIN}_pending_primary_success",
            )
        except Exception:  # noqa: BLE001
            pass

        self._switching = False

    async def start_failover_scanner(self) -> None:
        """Start the background task that finds a failover bridge."""
        if self._failover_scan_task is not None:
            return
        self._failover_scan_task = asyncio.create_task(
            self._failover_scan_loop()
        )
        self._health_monitor_task = asyncio.create_task(
            self._primary_health_loop()
        )

    async def _primary_health_loop(self) -> None:
        """Proactively monitor the primary connection and switch before commands fail.

        Checks every 5 seconds whether pydeako's connection is still alive.
        If it's dead AND a healthy failover is available, triggers the switch
        immediately — so the next user command hits the new bridge with zero failures.
        """
        await asyncio.sleep(15)  # let startup settle
        _status_counter = 0
        while not self._stopped:
            await asyncio.sleep(5)
            _status_counter += 1
            try:
                mgr = self.connection.connection_manager
                connected = mgr.connection is not None

                # Log status every 6 ticks (~30 seconds)
                if _status_counter % 6 == 0:
                    actual_ip = "unknown"
                    try:
                        if mgr.connection is not None:
                            actual_ip = mgr.connection.address.split(":")[0]
                    except (AttributeError, IndexError):
                        pass
                    fo_info = "none"
                    if self.failover_host:
                        fo_alive = (
                            self.failover_keepalive
                            and self.failover_keepalive.is_alive
                        )
                        fo_info = f"{self.failover_host} (keepalive={'up' if fo_alive else 'DOWN'})"
                    _LOGGER.info(
                        "Bridge status — primary: %s (connected=%s, stored=%s) | failover: %s",
                        actual_ip, connected, self.active_host, fo_info,
                    )

                # --- Pending primary retry (every ~30s) ---
                # If the user configured a primary that was offline, we
                # keep retrying until it wakes up (up to 48h).
                if (
                    self.pending_primary_host
                    and self.pending_primary_host != self.active_host
                    and not self._switching
                    and _status_counter % 6 == 0  # every ~30s
                ):
                    elapsed_h = (
                        time.monotonic() - self._pending_primary_since
                    ) / 3600
                    if elapsed_h > 48:
                        _LOGGER.error(
                            "Pending primary %s did not come online within "
                            "48 hours — giving up",
                            self.pending_primary_host,
                        )
                        try:
                            from homeassistant.components.persistent_notification import async_create  # noqa: PLC0415

                            async_create(
                                self.hass,
                                f"The Deako bridge at {self.pending_primary_host} "
                                f"did not come online within 48 hours. The "
                                f"integration is still running on "
                                f"{self.active_host}. You can try again via "
                                f"Settings → Devices & Services → Deako → "
                                f"Reconfigure.",
                                "Deako Bridge Change Failed",
                                f"{DOMAIN}_pending_primary_timeout",
                            )
                        except Exception:  # noqa: BLE001
                            pass
                        self.pending_primary_host = None
                    else:
                        _LOGGER.info(
                            "Pending primary retry: probing %s (%.1fh elapsed)",
                            self.pending_primary_host, elapsed_h,
                        )
                        if await _tcp_probe(
                            self.pending_primary_host, timeout=5.0
                        ):
                            _LOGGER.info(
                                "Pending primary %s is online! "
                                "Initiating voluntary switch",
                                self.pending_primary_host,
                            )
                            await self._switch_to_pending_primary()

                # --- Pending failover retry (every ~30s) ---
                # Same idea as pending primary but for the failover role.
                # We just need to open a keepalive socket, not a full
                # pydeako connection.
                if (
                    self.pending_failover_host
                    and self.pending_failover_host != self.active_host
                    and not self.failover_host  # don't retry if we already have one
                    and not self._switching
                    and _status_counter % 6 == 0  # every ~30s
                ):
                    elapsed_h = (
                        time.monotonic() - self._pending_failover_since
                    ) / 3600
                    if elapsed_h > 48:
                        _LOGGER.error(
                            "Pending failover %s did not come online within "
                            "48 hours — giving up",
                            self.pending_failover_host,
                        )
                        try:
                            from homeassistant.components.persistent_notification import async_create  # noqa: PLC0415

                            async_create(
                                self.hass,
                                f"The Deako failover bridge at "
                                f"{self.pending_failover_host} did not come "
                                f"online within 48 hours. The automatic "
                                f"failover scanner will continue looking for "
                                f"any available bridge. You can try again via "
                                f"Settings → Devices & Services → Deako → "
                                f"Reconfigure.",
                                "Deako Failover Bridge Change Failed",
                                f"{DOMAIN}_pending_failover_timeout",
                            )
                        except Exception:  # noqa: BLE001
                            pass
                        self.pending_failover_host = None
                    else:
                        _LOGGER.info(
                            "Pending failover retry: probing %s (%.1fh elapsed)",
                            self.pending_failover_host, elapsed_h,
                        )
                        if await _tcp_probe(
                            self.pending_failover_host, timeout=5.0
                        ):
                            _LOGGER.info(
                                "Pending failover %s is online! "
                                "Opening keepalive",
                                self.pending_failover_host,
                            )
                            target = self.pending_failover_host
                            keepalive = _FailoverKeepAlive(target)
                            loop = asyncio.get_event_loop()
                            if await keepalive.start(loop):
                                self.failover_host = target
                                self.failover_keepalive = keepalive
                                self.pending_failover_host = None
                                # Look up zc info
                                try:
                                    _zc = await zeroconf.async_get_instance(
                                        self.hass
                                    )
                                    fo_info = await self.hass.async_add_executor_job(
                                        _lookup_bridge_zeroconf, _zc, target
                                    )
                                    if fo_info:
                                        self.failover_zc_info = fo_info
                                except Exception:  # noqa: BLE001
                                    pass
                                _LOGGER.info(
                                    "Pending failover %s established", target
                                )
                                # Update device registry
                                try:
                                    entry = self.hass.config_entries.async_get_entry(
                                        self.entry_id
                                    )
                                    if entry:
                                        _store_known_bridge(
                                            self.hass, entry, target,
                                            self.failover_zc_info,
                                        )
                                        _update_bridge_device(
                                            self.hass, entry,
                                            self.active_host,
                                            self.active_zc_info,
                                            failover_host=target,
                                            failover_zc_info=self.failover_zc_info,
                                        )
                                except Exception:  # noqa: BLE001
                                    pass
                                # Notification
                                try:
                                    from homeassistant.components.persistent_notification import async_create  # noqa: PLC0415

                                    async_create(
                                        self.hass,
                                        f"The Deako failover bridge at "
                                        f"{target} is now online and "
                                        f"standing by as failover.",
                                        "Deako Failover Bridge Ready",
                                        f"{DOMAIN}_pending_failover_success",
                                    )
                                except Exception:  # noqa: BLE001
                                    pass
                            else:
                                keepalive.close()

                if connected:
                    # Check if pydeako silently reconnected to a different
                    # bridge (its internal auto-reconnect can land on any
                    # bridge advertising via mDNS).  If the actual IP
                    # changed, update our bookkeeping and device registry.
                    try:
                        real_ip = mgr.connection.address.split(":")[0]
                        if real_ip and real_ip != self.active_host:
                            _LOGGER.warning(
                                "Primary bridge IP changed: %s -> %s "
                                "(pydeako auto-reconnect)",
                                self.active_host, real_ip,
                            )
                            self.active_host = real_ip
                            # Look up fresh zeroconf info for the new bridge
                            try:
                                _zc = await zeroconf.async_get_instance(self.hass)
                                fresh = await self.hass.async_add_executor_job(
                                    _lookup_bridge_zeroconf, _zc, real_ip
                                )
                                if fresh:
                                    self.active_zc_info = fresh
                            except Exception:  # noqa: BLE001
                                pass
                            # Update device registry
                            try:
                                entry = self.hass.config_entries.async_get_entry(
                                    self.entry_id
                                )
                                if entry:
                                    _update_bridge_device(
                                        self.hass, entry, self.active_host,
                                        self.active_zc_info,
                                        failover_host=self.failover_host,
                                        failover_zc_info=self.failover_zc_info
                                        if self.failover_host else None,
                                    )
                            except Exception:  # noqa: BLE001
                                pass
                    except (AttributeError, IndexError):
                        pass
                    continue  # primary is healthy

                # Primary connection is dead
                if (
                    self.failover_host
                    and self.failover_keepalive
                    and self.failover_keepalive.is_alive
                    and not self._switching
                ):
                    _LOGGER.warning(
                        "Health monitor: primary connection lost, "
                        "proactively switching to failover %s",
                        self.failover_host,
                    )
                    await self._switch_to_failover()
                elif not self._switching:
                    _LOGGER.warning(
                        "Health monitor: primary connection lost "
                        "but no healthy failover available"
                    )
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Health monitor check error")

    async def _failover_scan_loop(self) -> None:
        """Periodically scan for a second Deako bridge to use as failover."""
        # Wait a bit after startup before scanning
        await asyncio.sleep(10)
        while not self._stopped:
            # If the user has a pending failover target, let the health
            # monitor handle retries for that specific device instead of
            # scanning for a random bridge.
            if self.pending_failover_host and not self.failover_host:
                await asyncio.sleep(FAILOVER_SCAN_INTERVAL_S)
                continue

            if self.failover_host and self.failover_keepalive:
                if self.failover_keepalive.is_alive:
                    # Keepalive socket is alive — trust it.
                    # Do NOT TCP probe here: Deako bridges only accept
                    # one TCP connection at a time, so a second probe
                    # would be rejected and we'd incorrectly conclude
                    # the bridge is offline.
                    await asyncio.sleep(FAILOVER_SCAN_INTERVAL_S)
                    continue
                # Keepalive died, need to find a new failover
                _LOGGER.info("Failover keepalive lost, scanning for new candidate")
                self.failover_keepalive.close()
                self.failover_keepalive = None
                self.failover_host = None
                self.failover_zc_info = {}
                # Update device registry to show failover lost
                try:
                    entry = self.hass.config_entries.async_get_entry(self.entry_id)
                    if entry:
                        _update_bridge_device(
                            self.hass, entry, self.active_host,
                            self.active_zc_info,
                            failover_host=None,
                        )
                except Exception:  # noqa: BLE001
                    pass

            # Don't scan while a failover switch is in progress —
            # active_host is changing and we'd pick up the wrong candidate
            if self._switching:
                await asyncio.sleep(5)
                continue

            # Scan for bridges via zeroconf
            _LOGGER.debug(
                "Failover scanner: scanning for candidates (active=%s)",
                self.active_host,
            )
            try:
                _zc = await zeroconf.async_get_instance(self.hass)
                bridges = await self.hass.async_add_executor_job(
                    _find_all_bridges_zeroconf, _zc
                )
            except Exception:  # noqa: BLE001
                _LOGGER.info("Failover scanner: mDNS browse failed")
                await asyncio.sleep(FAILOVER_SCAN_INTERVAL_S)
                continue

            _LOGGER.debug(
                "Failover scanner: found %d mDNS candidates: %s",
                len(bridges),
                list(bridges.keys()),
            )

            # Find a bridge that isn't the active primary
            for ip, info in bridges.items():
                if ip == self.active_host:
                    _LOGGER.debug(
                        "Failover scanner: skipping %s (is active primary)", ip
                    )
                    continue
                # TCP probe first — older devices may appear in zeroconf
                # but not actually be online (they don't announce disconnect)
                if not await _tcp_probe(ip):
                    _LOGGER.debug(
                        "Failover scanner: %s failed TCP probe, skipping", ip
                    )
                    continue
                # Re-check active_host — it may have changed during
                # the TCP probe (e.g. a failover switch just completed)
                if ip == self.active_host:
                    continue
                # Found a reachable candidate — try to open a keepalive socket
                _LOGGER.debug(
                    "Failover scanner: %s passed TCP probe, attempting keepalive", ip
                )
                keepalive = _FailoverKeepAlive(ip)
                loop = asyncio.get_event_loop()
                if await keepalive.start(loop):
                    # Final guard: make sure this isn't the current primary
                    if ip == self.active_host:
                        keepalive.close()
                        continue
                    self.failover_host = ip
                    self.failover_keepalive = keepalive
                    self.failover_zc_info = dict(info)
                    serial = info.get("serial", "unknown")
                    _LOGGER.info(
                        "Failover bridge ESTABLISHED: %s (SN: %s)",
                        ip,
                        serial,
                    )
                    # Store in known_bridges and update device registry
                    try:
                        entry = self.hass.config_entries.async_get_entry(
                            self.entry_id
                        )
                        if entry:
                            _store_known_bridge(self.hass, entry, ip, info)
                            _LOGGER.debug(
                                "Failover scanner: updating bridge device cards "
                                "(active=%s, failover=%s, fo_info=%s)",
                                self.active_host, ip, info,
                            )
                            _update_bridge_device(
                                self.hass, entry, self.active_host,
                                self.active_zc_info,
                                failover_host=ip,
                                failover_zc_info=info,
                            )
                            _LOGGER.debug(
                                "Failover scanner: bridge device cards updated OK"
                            )
                        else:
                            _LOGGER.debug(
                                "Failover scanner: config entry not found!"
                            )
                    except Exception as exc:  # noqa: BLE001
                        _LOGGER.debug(
                            "Failover scanner: error updating device cards: %s", exc
                        )
                    break
                _LOGGER.debug(
                    "Failover scanner: keepalive to %s failed to start", ip
                )
                keepalive.close()

            await asyncio.sleep(FAILOVER_SCAN_INTERVAL_S)

    def stop(self) -> None:
        """Stop all background tasks and clean up."""
        self._stopped = True
        if self._failover_scan_task is not None:
            self._failover_scan_task.cancel()
            self._failover_scan_task = None
        if self._health_monitor_task is not None:
            self._health_monitor_task.cancel()
            self._health_monitor_task = None
        if self.failover_keepalive is not None:
            self.failover_keepalive.close()
            self.failover_keepalive = None


async def _tcp_probe(host: str, port: int = DEAKO_DEFAULT_PORT, timeout: float = 3.0) -> bool:
    """Quick TCP probe to check if a host is actually reachable on port 23.

    Older Deako devices don't announce disconnection from the network,
    so zeroconf may show stale entries. This probe verifies the device
    is actually online and accepting connections.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


def _find_all_bridges_zeroconf(zc: Zeroconf_) -> dict[str, dict[str, str]]:
    """Find all Deako bridges via active mDNS browse.

    Uses a ServiceBrowser to actively query the network for Deako
    devices, rather than just reading the zeroconf cache (which may
    be stale or empty). Waits up to 5 seconds for responses.

    Returns {ip: {"serial": ..., "version": ...}} for all bridges found.
    """
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

    # Wait up to 5 seconds, checking periodically for results
    deadline = _time.monotonic() + 5.0
    while _time.monotonic() < deadline:
        _time.sleep(0.5)
        if collector.names:
            # Give a bit more time for additional responses
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
    """Create or update bridge devices in HA's device registry.

    Creates a primary bridge device card and, if a failover is known,
    a separate failover bridge device card. Each gets its own clean
    entry with SN, FW, and IP.
    """
    device_reg = dr.async_get(hass)

    # --- Primary bridge device ---
    bridge_serial = active_zc_info.get("serial", "")
    bridge_fw = active_zc_info.get("version", "")

    bridge_name = f"{NAME} Bridge (Primary)"

    # The primary card always uses entry_id as its stable identifier.
    # async_get_or_create will find and update it in place when the
    # physical device (serial) changes — no need to delete/recreate.
    # Use ONLY entry_id as the identifier — never the serial.
    # Including the serial causes cross-matching: when a device
    # changes roles (failover→primary), async_get_or_create finds
    # the old failover card by serial instead of the primary card
    # by entry_id, creating orphaned duplicate cards.
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
    # Force-set exact identifiers and clear stale attributes.
    update_kwargs: dict = {}
    if primary_device.identifiers != identifiers:
        update_kwargs["new_identifiers"] = identifiers
    if primary_device.serial_number != (bridge_serial or None):
        update_kwargs["serial_number"] = bridge_serial or None
    if primary_device.sw_version != (bridge_fw or None):
        update_kwargs["sw_version"] = bridge_fw or None
    if update_kwargs:
        device_reg.async_update_device(primary_device.id, **update_kwargs)
    _LOGGER.debug(
        "_update_bridge_device: primary card — "
        "device_id=%s, identifiers=%s",
        primary_device.id, identifiers,
    )


    # --- Failover bridge device (separate card) ---
    if failover_host:
        # Use provided zc_info, fall back to known_bridges, or empty
        fo_zc = failover_zc_info or {}
        if not fo_zc.get("serial"):
            known = entry.data.get(CONF_KNOWN_BRIDGES, {})
            if failover_host in known:
                fo_zc = {**fo_zc, **known[failover_host]}

        fo_serial = fo_zc.get("serial", "")
        fo_fw = fo_zc.get("version", "")

        fo_name = f"{NAME} Bridge (Failover)"

        # Use ONLY the _failover suffix as identifier — never the serial.
        # (Same reason as primary: serial causes cross-matching.)
        fo_identifiers: set[tuple[str, str]] = {
            (DOMAIN, f"{entry.entry_id}_failover")
        }

        _LOGGER.debug(
            "_update_bridge_device: creating failover card — "
            "identifiers=%s, name=%s, host=%s",
            fo_identifiers, fo_name, failover_host,
        )

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
        # Force-set exact identifiers and clear stale attributes.
        # async_get_or_create only adds — never removes stale serials
        # or firmware from a previous physical device in this role.
        update_kwargs: dict = {}
        if fo_device.identifiers != fo_identifiers:
            update_kwargs["new_identifiers"] = fo_identifiers
        if fo_device.serial_number != (fo_serial or None):
            update_kwargs["serial_number"] = fo_serial or None
        if fo_device.sw_version != (fo_fw or None):
            update_kwargs["sw_version"] = fo_fw or None
        if update_kwargs:
            device_reg.async_update_device(fo_device.id, **update_kwargs)
        _LOGGER.debug(
            "_update_bridge_device: failover card — "
            "device_id=%s, identifiers=%s",
            fo_device.id, fo_identifiers,
        )
    else:
        # No failover — remove stale failover card if it exists
        fo_id = (DOMAIN, f"{entry.entry_id}_failover")
        for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
            if fo_id in device.identifiers:
                _LOGGER.debug("Removing stale failover bridge card (no failover active)")
                device_reg.async_remove_device(device.id)
                break


type DeakoConfigEntry = ConfigEntry[DeakoRuntimeData]


async def _try_connect(host: str) -> Deako | None:
    """Try to connect to a Deako bridge at the given host. Returns Deako or None."""

    async def get_address():
        return f"{host}:{DEAKO_DEFAULT_PORT}", NAME

    connection = Deako(get_address)
    try:
        await connection.connect()
        await connection.find_devices()
    except (FindDevicesError, OSError) as exc:
        _LOGGER.info("Failed to connect to %s: %s", host, exc)
        try:
            await connection.disconnect()
        except Exception:  # noqa: BLE001
            pass
        return None

    devices = connection.get_devices()
    if len(devices) == 0:
        _LOGGER.info("Connected to %s but no devices found", host)
        await connection.disconnect()
        return None

    return connection


async def async_setup_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> bool:
    """Set up deako."""
    primary_host = entry.data.get(CONF_HOST)
    secondary_host = entry.data.get(CONF_SECONDARY_HOST)
    connection: Deako | None = None
    active_host: str | None = None

    # Try primary host first
    if primary_host:
        _LOGGER.info("Attempting connection to primary bridge: %s", primary_host)
        connection = await _try_connect(primary_host)
        if connection:
            active_host = primary_host

    # Fall back to secondary host
    if connection is None and secondary_host:
        _LOGGER.warning(
            "Primary bridge unavailable, trying secondary: %s", secondary_host
        )
        await asyncio.sleep(2)
        connection = await _try_connect(secondary_host)
        if connection:
            active_host = secondary_host

    # Fall back to zeroconf discovery
    if connection is None:
        if primary_host or secondary_host:
            _LOGGER.warning(
                "Both configured bridges unavailable, falling back to discovery"
            )
            # Give the bridge time to recover from failed connection attempts.
            # Deako bridges can lock up if connections are opened/closed rapidly.
            await asyncio.sleep(3)
        _zc = await zeroconf.async_get_instance(hass)
        discoverer = DeakoDiscoverer(_zc)
        connection = Deako(discoverer.get_address)
        active_host = "discovered"

        await connection.connect()
        try:
            await connection.find_devices()
        except FindDevicesError as exc:
            _LOGGER.info("Error finding devices via discovery: %s", exc)
            await connection.disconnect()
            raise ConfigEntryNotReady(exc) from exc

        devices = connection.get_devices()
        if len(devices) == 0:
            await connection.disconnect()
            raise ConfigEntryNotReady(devices)

    # Get the actual connected IP from pydeako's connection manager.
    # This is authoritative — don't rely on the zeroconf cache which
    # may return a different bridge than the one we actually connected to.
    if active_host == "discovered":
        try:
            conn_address = connection.connection_manager.connection.address
            # address is "ip:port" format
            active_host = conn_address.split(":")[0]
            _LOGGER.debug(
                "Resolved actual connected address: %s", active_host
            )
        except (AttributeError, IndexError):
            _LOGGER.debug("Could not resolve connected address from pydeako")

    # Look up zeroconf info for the active bridge (serial, firmware)
    zc_info: dict[str, str] = {}
    lookup_host = active_host if active_host != "discovered" else None
    try:
        _zc = await zeroconf.async_get_instance(hass)
        zc_info = await hass.async_add_executor_job(
            _lookup_bridge_zeroconf, _zc, lookup_host
        )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not look up zeroconf info for bridge")

    # Fall back to known_bridges if zeroconf didn't return serial/version
    if not zc_info.get("serial"):
        known = entry.data.get(CONF_KNOWN_BRIDGES, {})
        if active_host and active_host in known:
            stored = known[active_host]
            if stored.get("serial"):
                zc_info.setdefault("serial", stored["serial"])
            if stored.get("version"):
                zc_info.setdefault("version", stored["version"])

    # If a secondary host was manually configured, use it as the initial
    # failover target — but only if it's a DIFFERENT host than the active one.
    # When the primary is offline and we fall back to the secondary, they're
    # the same IP and we must NOT treat the active bridge as its own failover.
    initial_failover: str | None = None
    if secondary_host and secondary_host != active_host:
        initial_failover = secondary_host

    # Register the bridge as a device so it's visible in the UI
    _update_bridge_device(
        hass, entry, active_host, zc_info,
        failover_host=initial_failover,
        failover_zc_info=None,
    )

    _LOGGER.info("Deako bridge active on: %s", active_host)

    # Persist this bridge in known_bridges for future reconfigure dropdowns.
    _store_known_bridge(hass, entry, active_host, zc_info)

    # Detect if the configured primary is offline (we fell back to
    # another bridge).  If so, mark it as a "pending primary" so the
    # health monitor keeps retrying until it comes online.
    pending_primary: str | None = None
    if (
        primary_host
        and active_host != primary_host
        and primary_host != "discovered"
    ):
        pending_primary = primary_host
        _LOGGER.warning(
            "Configured primary %s is offline. Running on %s. "
            "Will retry %s in the background (up to 48h).",
            primary_host, active_host, primary_host,
        )

    entry.runtime_data = DeakoRuntimeData(
        hass=hass,
        entry_id=entry.entry_id,
        connection=connection,
        active_host=active_host,
        active_zc_info=dict(zc_info) if zc_info else {},
        failover_host=initial_failover,
        pending_primary_host=pending_primary,
        _pending_primary_since=time.monotonic() if pending_primary else 0.0,
    )

    # If a manual secondary was configured, open the keepalive immediately
    if initial_failover:
        keepalive = _FailoverKeepAlive(initial_failover)
        loop = asyncio.get_event_loop()
        if await keepalive.start(loop):
            entry.runtime_data.failover_keepalive = keepalive
            _LOGGER.info("Failover keepalive established to %s", initial_failover)
        else:
            _LOGGER.warning(
                "Could not establish failover keepalive to %s — "
                "setting as pending failover (will retry up to 48h)",
                initial_failover,
            )
            entry.runtime_data.failover_host = None
            entry.runtime_data.pending_failover_host = initial_failover
            entry.runtime_data._pending_failover_since = time.monotonic()

    # Start background scanner to auto-discover a failover bridge
    await entry.runtime_data.start_failover_scanner()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove stale devices that are no longer on the bridge.
    # After a reload, the bridge may report fewer devices than HA has
    # registered (e.g. a switch was removed from the Deako app).
    # We clean those up automatically so the user doesn't have to.
    device_reg = dr.async_get(hass)
    current_uuids = set(connection.get_devices().keys())
    # Build set of identifiers we want to KEEP:
    #   - All current light devices: (DOMAIN, uuid)
    #   - Primary bridge card: (DOMAIN, entry.entry_id)
    #   - Failover bridge card (only if failover is active)
    keep_ids = {(DOMAIN, uuid) for uuid in current_uuids}
    keep_ids.add((DOMAIN, entry.entry_id))
    if entry.runtime_data.failover_host:
        keep_ids.add((DOMAIN, f"{entry.entry_id}_failover"))

    for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
        # A device belongs to this integration if any of its identifiers
        # are in the DOMAIN.  Remove it only if NONE of its identifiers
        # are in our keep set.
        dominated = {id_pair for id_pair in device.identifiers if id_pair[0] == DOMAIN}
        if dominated and not dominated & keep_ids:
            _LOGGER.info(
                "Removing stale device %s (%s) — no longer on bridge",
                device.name, dominated,
            )
            device_reg.async_remove_device(device.id)

    return True


def _store_known_bridge(
    hass: HomeAssistant,
    entry: ConfigEntry,
    host: str | None,
    zc_info: dict[str, str],
) -> None:
    """Store a bridge in the known_bridges dict in config entry data."""
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


async def async_unload_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop failover scanner and keepalive
    entry.runtime_data.stop()

    await entry.runtime_data.connection.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
