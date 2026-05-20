"""PowersensorMessageDispatcher is the main coordinator of messages.

The classes and utilities here mediate Powersensor PlugApi messages and
updates/creation of Home Assistant entities.
"""

from collections.abc import Callable
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address as _parse_ip
import logging
from typing import Any

from powersensor_local import PlugApi, VirtualHousehold

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_call_later

from .const import (
    CFG_DEVICES,
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    PLUG_ADDED_TO_HA_SIGNAL,
    ROLE_UNKNOWN,
    ROLE_UPDATE_SIGNAL,
    SENSOR_ADDED_TO_HA_SIGNAL,
    ZEROCONF_ADD_PLUG_SIGNAL,
    ZEROCONF_REMOVE_PLUG_SIGNAL,
    ZEROCONF_UPDATE_PLUG_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)


def _to_ip_str(host: int | str | bytes | IPv4Address | IPv6Address) -> str:
    """Return a dotted-decimal string from any IP representation.

    ZeroconfServiceInfo.host has returned plain strings, IPv4Address objects,
    and raw integers depending on the HA/zeroconf version in use.
    """
    if isinstance(host, str):
        return host
    return str(_parse_ip(host))


async def _handle_exception(event: str, exc: BaseException) -> None:
    """Log errors raised by PlugApi."""
    _LOGGER.error(
        "On event %s plug connection reported exception: %s",
        event,
        exc,
        exc_info=exc,
    )


def _filter_unknown(role: str | None) -> str | None:
    """Return None when role is the sentinel ROLE_UNKNOWN string."""
    return None if role == ROLE_UNKNOWN else role


class PowersensorMessageDispatcher:
    """Mediates PlugApi push messages and HA entity lifecycle signals."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vhh: VirtualHousehold,
        debounce_timeout: float = 60,
    ) -> None:
        """Initialise the dispatcher.

        Args:
            hass: The Home Assistant instance.
            entry: The config entry this dispatcher belongs to.
            vhh: The VirtualHousehold calculation engine.
            debounce_timeout: Seconds to wait before treating a disappeared
                plug/service as truly gone.
        """
        self._hass = hass
        self._entry = entry
        self._vhh = vhh
        self.plugs: dict[str, PlugApi] = {}
        self._known_plugs: set[str] = set()
        self._known_plug_names: dict[str, str] = {}
        self.sensors: dict[str, str | None] = {}
        self._on_start_sensor_queue: dict[str, str | None] = {}
        self._pending_removals: dict[str, Callable[[], None]] = {}
        self._debounce_seconds = debounce_timeout

        self._unsubscribe_from_signals = [
            async_dispatcher_connect(
                self._hass, ZEROCONF_ADD_PLUG_SIGNAL, self._plug_added
            ),
            async_dispatcher_connect(
                self._hass, ZEROCONF_UPDATE_PLUG_SIGNAL, self._plug_updated
            ),
            async_dispatcher_connect(
                self._hass, ZEROCONF_REMOVE_PLUG_SIGNAL, self._schedule_plug_removal
            ),
            async_dispatcher_connect(
                self._hass,
                PLUG_ADDED_TO_HA_SIGNAL,
                self._acknowledge_plug_added_to_homeassistant,
            ),
            async_dispatcher_connect(
                self._hass,
                SENSOR_ADDED_TO_HA_SIGNAL,
                self._acknowledge_sensor_added_to_homeassistant,
            ),
        ]

        # Plug-queue state
        # Plug-queue state: keyed by MAC so that a re-announcement of the same
        # plug always overwrites the previous entry rather than accumulating
        # stale tuples that can never be discarded by an exact-match set.discard().
        self._plug_added_queue: dict[str, tuple[str, int, str]] = {}

    # ------------------------------------------------------------------
    # Plug queue management
    # ------------------------------------------------------------------

    def enqueue_plug_for_adding(
        self, mac: str, host: str, port: int, name: str
    ) -> None:
        """Buffer a plug until its HA entity and API can be created."""
        _LOGGER.debug("Adding to plug processing queue: mac=%s host=%s", mac, host)
        self._plug_added_queue[mac] = (host, port, name)

    def process_plug_queue(self) -> None:
        """Process all queued plugs immediately.

        Called by ``__init__.py`` after ``async_forward_entry_setups`` returns,
        which guarantees the sensor platform (and its ``CREATE_PLUG_SIGNAL``
        listener) is fully set up before this runs.  No polling or timing
        assumptions are needed.
        """
        if not self._plug_added_queue:
            return

        for mac_address, (host, port, name) in list(self._plug_added_queue.items()):
            try:
                if not self._plug_has_been_seen(mac_address, name):
                    async_dispatcher_send(
                        self._hass,
                        CREATE_PLUG_SIGNAL,
                        mac_address,
                        host,
                        port,
                        name,
                    )
                    # Discard now; _acknowledge_plug_added_to_homeassistant
                    # will call _create_api via PLUG_ADDED_TO_HA_SIGNAL and
                    # does its own pop — but we must not leave a stale entry
                    # here in case that signal is lost or arrives with a
                    # different tuple.
                    self._plug_added_queue.pop(mac_address, None)
                elif mac_address in self._known_plugs and mac_address not in self.plugs:
                    _LOGGER.info(
                        "Plug %s is known but API is missing - reconnecting without "
                        "requesting entity creation",
                        mac_address,
                    )
                    self._create_api(mac_address, host, port, name)
                    self._plug_added_queue.pop(mac_address, None)
                else:
                    _LOGGER.debug(
                        "Plug %s already created as a HA entity - flushing from queue",
                        mac_address,
                    )
                    self._plug_added_queue.pop(mac_address, None)
            except Exception:
                _LOGGER.exception(
                    "Error processing plug queue entry for mac=%s; skipping",
                    mac_address,
                )

    def _plug_has_been_seen(self, mac_address: str, name: str) -> bool:
        return (
            mac_address in self.plugs
            or mac_address in self._known_plugs
            or name in self._known_plug_names
        )

    # ------------------------------------------------------------------
    # Sensor queue management
    # ------------------------------------------------------------------

    def drain_on_start_sensor_queue(self) -> list[tuple[str, str | None]]:
        """Return all queued startup sensors and clear the queue.

        Sensors whose relay announcements arrived before the sensor platform
        was ready are buffered here.  ``sensor.py`` calls this once after
        ``async_forward_entry_setups`` returns so those sensors are not missed.
        """
        items = list(self._on_start_sensor_queue.items())
        self._on_start_sensor_queue.clear()
        return items

    # ------------------------------------------------------------------
    # Plug removal debouncing
    # ------------------------------------------------------------------

    def _cancel_any_pending_removal(self, mac: str, source: str) -> None:
        """Cancel a scheduled plug removal, e.g. because the plug reappeared.

        This is now synchronous: ``async_call_later`` returns a plain cancel
        callback, so no ``await`` is needed.
        """
        cancel = self._pending_removals.pop(mac, None)
        if cancel:
            cancel()
            _LOGGER.debug("Cancelled pending removal for %s by %s", mac, source)

    def _schedule_removal(self, mac: str, name: str) -> None:
        """Schedule plug removal after the debounce period using async_call_later."""

        @callback
        def _do_remove(_now: datetime) -> None:
            self._pending_removals.pop(mac, None)
            _LOGGER.debug(
                "Plug %s still absent after timeout - processing removal", mac
            )
            self._hass.async_create_background_task(
                self._disconnect_plug(mac, name),
                name=f"Removal-Task-For-{name}",
            )

        self._pending_removals[mac] = async_call_later(
            self._hass, self._debounce_seconds, _do_remove
        )

    async def _disconnect_plug(self, mac: str, name: str) -> None:
        """Disconnect and deregister a plug API."""
        if mac in self.plugs:
            await self.plugs.pop(mac).disconnect()
        self._known_plug_names.pop(name, None)
        _LOGGER.info("API for plug %s disconnected and removed", mac)

    @callback
    def _persist_plug_info(self, mac: str, host: str, port: int, name: str) -> None:
        """Write updated plug host/port/name into entry.data[CFG_DEVICES].

        Called when mDNS reports a changed address for a known plug.  Persists
        the current address so the next restart enqueues the correct host/port
        from storage rather than a stale one.

        Uses async_update_entry without changing version/minor_version, which
        writes to .storage in place without triggering a config-entry reload.
        """
        if self._entry.state is not ConfigEntryState.LOADED:
            # Entry is not registered with the config_entries store yet (e.g.
            # during initial setup or in tests that use a bare Mock entry).
            # Skip writing the data— the correct address will be persisted once the
            # entry reaches LOADED state and a real async_update_entry is safe.
            _LOGGER.debug(
                "Skipping persist for plug %s — entry not in LOADED state (%s)",
                mac,
                self._entry.state,
            )
            return
        devices: dict[str, dict[Any, Any]] = dict(self._entry.data.get(CFG_DEVICES, {}))
        existing = dict(devices.get(mac, {}))
        existing.update({"host": host, "port": port, "name": name, "mac": mac})
        devices[mac] = existing
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CFG_DEVICES: devices},
        )
        _LOGGER.debug("Persisted updated address for plug %s: %s:%s", mac, host, port)

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    def _get_role_info(self, message: dict[str, Any]) -> tuple[str | None, str | None]:
        """Return (reported_role, persisted_role) for the MAC in *message*."""
        persisted_role = _filter_unknown(
            self._entry.data.get(CFG_ROLES, {}).get(message["mac"])
        )
        role = _filter_unknown(message.get("role"))
        return role, persisted_role

    # ------------------------------------------------------------------
    # Inbound zeroconf signals
    # ------------------------------------------------------------------

    @callback
    def _plug_added(self, info: dict[str, Any]) -> None:
        _LOGGER.debug("Request to add plug received: %s", info)
        mac = info["properties"][b"id"].decode("utf-8")
        self._cancel_any_pending_removal(mac, "request to add plug")
        self.enqueue_plug_for_adding(
            mac, _to_ip_str(info["addresses"][0]), info["port"], info["name"]
        )
        self.process_plug_queue()

    @callback
    def _plug_updated(self, info: dict[str, Any]) -> None:
        _LOGGER.debug("Request to update plug received: %s", info)
        mac = info["properties"][b"id"].decode("utf-8")
        self._cancel_any_pending_removal(mac, "request to update plug")
        host = _to_ip_str(info["addresses"][0])
        port = info["port"]
        name = info["name"]

        if mac in self.plugs:
            current_api: PlugApi = self.plugs[mac]
            if current_api.ip_address == host and current_api.port == port:
                _LOGGER.debug("Plug %s update does not change IP/port - skipping", mac)
                return
            # Pop the stale API from the dict immediately, before scheduling
            # the background disconnect.  If we left it in self.plugs and
            # scheduled _disconnect_plug(mac, name), the background task would
            # race with the _create_api() call below: by the time the task ran,
            # self.plugs[mac] would already point to the new API, so the task
            # would pop and disconnect the new connection instead of the stale
            # one, leaving the plug orphaned.
            #
            # We intentionally do NOT touch _known_plug_names here — _create_api
            # will overwrite it with the same name→mac mapping anyway, and
            # removing it first would create a brief window where
            # _schedule_plug_removal could incorrectly warn about an unknown name.
            stale_api: PlugApi = self.plugs.pop(mac)
            self._hass.async_create_background_task(
                stale_api.disconnect(),
                name=f"powersensor-disconnect-{mac}",
            )

        # Persist the refreshed address so the next restart enqueues the
        # correct host/port from storage rather than a stale one.
        self._persist_plug_info(mac, host, port, name)

        if mac in self._known_plugs:
            self._create_api(mac, host, port, name)
        else:
            self.enqueue_plug_for_adding(mac, host, port, name)
            self.process_plug_queue()

    @callback
    def _schedule_plug_removal(self, name: str, info: dict[str, Any]) -> None:
        _LOGGER.debug("Request to remove plug received: %s", info)
        if name not in self._known_plug_names:
            _LOGGER.warning(
                "Received removal request for unknown gateway name [%s] - ignoring",
                name,
            )
            return

        mac = self._known_plug_names[name]
        if mac in self.plugs and mac not in self._pending_removals:
            _LOGGER.debug("Scheduling removal for %s", name)
            self._schedule_removal(mac, name)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def handle_relaying_for(self, event: str, message: dict[str, Any]) -> None:
        """Handle a relay announcement that may introduce a new sensor."""
        mac = message.get("mac")
        device_type = message.get("device_type")
        if mac is None or device_type != "sensor":
            _LOGGER.debug(
                'Ignoring relayed device with MAC "%s" and type %s', mac, device_type
            )
            return

        role, persisted_role = self._get_role_info(message)
        _LOGGER.debug("Relayed sensor %s with role %s found", mac, role)

        if mac not in self.sensors:
            _LOGGER.debug("Reporting new sensor %s with role %s", mac, role)
            self._on_start_sensor_queue[mac] = role
            async_dispatcher_send(self._hass, CREATE_SENSOR_SIGNAL, mac, role)

        if persisted_role is not None and role != persisted_role:
            _LOGGER.debug(
                "Restoring role for %s from %s to %s", mac, role, persisted_role
            )
            async_dispatcher_send(self._hass, ROLE_UPDATE_SIGNAL, mac, persisted_role)

    async def handle_message(self, event: str, message: dict[str, Any]) -> None:
        """Route a PlugApi push message to the appropriate HA signals.

        Must be ``async def``: PlugApi.subscribe awaits every registered
        callback, so a plain synchronous function would be wrapped as a
        coroutine and its return value silently discarded.  The ``await``
        calls to ``self._vhh.process_*`` also require an async context.
        The HA dispatcher calls (``async_dispatcher_send``) are synchronous
        and do not themselves need ``await``.
        """
        mac = message["mac"]
        role, persisted_role = self._get_role_info(message)

        message["role"] = persisted_role if role is None else role

        if role is not None and role != persisted_role:
            self.sensors[mac] = role
            async_dispatcher_send(self._hass, ROLE_UPDATE_SIGNAL, mac, role)

        self._cancel_any_pending_removal(mac, "new message received from plug")

        if event == "average_power":
            await self._vhh.process_average_power_event(message)
        elif event == "summation_energy":
            await self._vhh.process_summation_event(message)

        async_dispatcher_send(
            self._hass,
            f"{DATA_UPDATE_SIGNAL_PREFIX}{mac}_{event}",
            event,
            message,
        )

        # Synthesise a role-type message for the role diagnostic entity.
        # Use message["role"] (the effective role) rather than the raw `role`
        # variable, which may be None when a persisted role has been substituted.
        async_dispatcher_send(
            self._hass,
            f"{DATA_UPDATE_SIGNAL_PREFIX}{mac}_role",
            "role",
            {"role": message["role"]},
        )

    # ------------------------------------------------------------------
    # Acknowledgement callbacks
    # ------------------------------------------------------------------

    @callback
    def _acknowledge_sensor_added_to_homeassistant(
        self, mac: str, role: str | None
    ) -> None:
        self.sensors[mac] = role

    @callback
    def _acknowledge_plug_added_to_homeassistant(
        self, mac_address: str, host: str, port: int, name: str
    ) -> None:
        self._create_api(mac_address, host, port, name)
        self._plug_added_queue.pop(mac_address, None)

    # ------------------------------------------------------------------
    # API creation
    # ------------------------------------------------------------------

    def _create_api(self, mac_address: str, ip: str, port: int, name: str) -> None:
        _LOGGER.info("Creating API for mac=%s, ip=%s, port=%s", mac_address, ip, port)
        self._known_plugs.add(mac_address)
        self._known_plug_names[name] = mac_address

        # Normalise ip to a plain string — ZeroconfServiceInfo.host has returned
        # integers, IPv4Address objects, or strings depending on HA/zeroconf version.
        ip = _to_ip_str(ip)

        known_events = [
            "average_flow",
            "average_power",
            "average_power_components",
            "battery_level",
            "radio_signal_quality",
            "summation_energy",
            "summation_volume",
        ]

        api = PlugApi(mac_address, ip, port)
        self.plugs[mac_address] = api
        for ev in known_events:
            api.subscribe(ev, self.handle_message)
        api.subscribe("now_relaying_for", self.handle_relaying_for)
        api.subscribe("exception", _handle_exception)
        api.connect()

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def stop_pending_removal_tasks(self) -> None:
        """Cancel all outstanding plug-removal timers."""
        for cancel in list(self._pending_removals.values()):
            cancel()
        self._pending_removals.clear()

    async def disconnect(self) -> None:
        """Disconnect all plug APIs and clean up."""
        while self.plugs:
            _, api = self.plugs.popitem()
            await api.disconnect()

        for unsubscribe in self._unsubscribe_from_signals:
            if unsubscribe is not None:
                unsubscribe()

        await self.stop_pending_removal_tasks()
