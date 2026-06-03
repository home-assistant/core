"""PowersensorMessageDispatcher routes PowersensorDevices events to HA entities.

The dispatcher owns a single PowersensorDevices instance (from powersensor_local)
which handles all plug connections, reconnections, and sensor discovery internally.
The dispatcher's sole responsibility is to translate the unified event stream into
HA dispatcher signals that drive entity creation and data updates.

Event routing:
  device_found  (device_type=plug)    → CREATE_PLUG_SIGNAL
  device_found  (device_type=sensor)  → CREATE_SENSOR_SIGNAL
  device_lost                         → logged (library handles reconnection)
  average_power, summation_energy,    → DATA_UPDATE_SIGNAL_PREFIX + mac + event
    and all other measurement events    (also fed into VirtualHousehold)

Discovery lifecycle
-------------------
devices.start() runs a UDP broadcast scan and fires device_found synchronously
for every responding plug before returning.  The platform (sensor.py) is set up
before start() is called, so its signal listeners are always ready when those
events arrive.

Subsequent rescans (periodic and on-startup graduated delays) call devices.rescan(),
which re-runs the scan.  The library deduplicates: _add_device only fires
device_found for MACs not already in its internal _devices dict, so rescans are
safe and idempotent.  The dispatcher mirrors this with its own plugs/sensors sets
so that a rescan finding a previously missed plug still creates its entities even
after the first scan completed without it.

Sleep/wake recovery
-------------------
After a laptop sleep, the library's expiry timer fires and removes devices from its
internal _devices dict (since no data arrived while asleep).  The next rescan then
re-adds them and fires device_found again.  When that happens, the MAC is already
in self.plugs / self.sensors (from before the sleep), so we skip the CREATE signal
to avoid duplicate entities — but we MUST still call devices.subscribe(mac) because
the re-added _Device object starts with subscribed=False.  Without this re-subscribe,
_emit_if_subscribed silently drops all events and the sensors appear permanently dead.
"""

import logging
from typing import Any

from powersensor_local import VirtualHousehold

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    ROLE_UNKNOWN,
    ROLE_UPDATE_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)


def _filter_unknown(role: str | None) -> str | None:
    """Return None when role is the sentinel ROLE_UNKNOWN string."""
    return None if role == ROLE_UNKNOWN else role


class PowersensorMessageDispatcher:
    """Routes PowersensorDevices events to HA entity lifecycle signals."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vhh: VirtualHousehold,
    ) -> None:
        """Initialise the dispatcher.

        Args:
            hass: The Home Assistant instance.
            entry: The config entry this dispatcher belongs to.
            vhh: The VirtualHousehold calculation engine.
        """
        self._hass = hass
        self._entry = entry
        self._vhh = vhh

        # Tracks known devices so that rescans don't create duplicate entities.
        # The library deduplicates on its side too, but we guard here as well
        # since sensor.py has no other way to detect a duplicate CREATE signal.
        self.plugs: set[str] = set()
        self.sensors: dict[str, str | None] = {}

    # ------------------------------------------------------------------
    # PowersensorDevices unified event callback
    # ------------------------------------------------------------------

    async def on_device_event(self, event: dict[str, Any]) -> None:
        """Handle all events from the PowersensorDevices unified stream.

        This is the single callback passed to PowersensorDevices.start().
        """
        event_type = event.get("event")

        match event_type:
            case "device_found":
                await self._handle_device_found(event)
            case "device_lost":
                self._handle_device_lost(event)
            case "scan_complete":
                _LOGGER.debug(
                    "Scan complete, %d gateway(s) found", event.get("gateway_count", 0)
                )
            case _:
                if event_type is not None:
                    await self._handle_measurement(event_type, event)

    async def _handle_device_found(self, event: dict[str, Any]) -> None:
        """Handle a newly discovered plug or sensor.

        The library emits device_found for both plugs (found via UDP broadcast
        scan) and sensors (found when a plug relays a now_relaying_for message,
        which the library converts to a device_found internally).

        Note: the library drops the role when converting now_relaying_for →
        device_found (_add_device only receives the type string), so
        event.get("role") is always None for sensors.  We fall back to the
        role persisted in entry.data from the previous session so that
        role-gated entities (power, energy, water flow, etc.) are created
        immediately on reload rather than waiting for the first measurement
        to trigger ROLE_UPDATE_SIGNAL.

        Re-subscribe after expiry: if the MAC is already known (i.e. we have
        entities for it) but the library re-fired device_found because its
        internal _Device was removed by the expiry timer and then re-added by a
        rescan, we skip the CREATE signal (no duplicate entities) but still call
        devices.subscribe(mac).  The library creates a fresh _Device with
        subscribed=False, so without this call _emit_if_subscribed would silently
        discard all subsequent events.
        """
        mac = event.get("mac")
        # note: library has trailing colon, that may change in the future.
        device_type = event.get("device_type")
        if mac is None:
            return

        if device_type == "plug":
            if mac not in self.plugs:
                _LOGGER.debug("New plug discovered: %s", mac)
                self.plugs.add(mac)
                self._entry.runtime_data.devices.subscribe(mac)
                async_dispatcher_send(self._hass, CREATE_PLUG_SIGNAL, mac)
            else:
                # MAC already known — device was removed by expiry timer and
                # re-added by rescan.  Re-subscribe so events flow again.
                _LOGGER.debug(
                    "Plug re-discovered after expiry, re-subscribing: %s", mac
                )
                self._entry.runtime_data.devices.subscribe(mac)

        elif device_type == "sensor":
            role = _filter_unknown(event.get("role"))
            if mac not in self.sensors:
                # The library never populates role in the device_found event for
                # sensors (it is lost in the now_relaying_for → _add_device
                # conversion).  Fall back to the persisted role so that
                # role-gated entities are created correctly on reload/reboot.
                if role is None:
                    role = _filter_unknown(self._entry.data.get(CFG_ROLES, {}).get(mac))
                _LOGGER.debug("New sensor discovered: %s role=%s", mac, role)
                self.sensors[mac] = role
                self._entry.runtime_data.devices.subscribe(mac)
                async_dispatcher_send(self._hass, CREATE_SENSOR_SIGNAL, mac, role)
            else:
                # MAC already known — re-subscribe after expiry (same as plug case).
                _LOGGER.debug(
                    "Sensor re-discovered after expiry, re-subscribing: %s", mac
                )
                self._entry.runtime_data.devices.subscribe(mac)

    def _handle_device_lost(self, event: dict[str, Any]) -> None:
        """Handle a plug or sensor going offline.

        The library manages reconnection internally, so we don't remove entities.
        Entities naturally become unavailable when their data update timeout fires.
        """
        mac = event.get("mac")
        if mac is None:
            return
        _LOGGER.info("Device lost: %s", mac)

    async def _handle_measurement(
        self, event_type: str, message: dict[str, Any]
    ) -> None:
        """Route a measurement event to the appropriate HA signals."""
        mac = message.get("mac")
        if mac is None:
            return

        role = _filter_unknown(message.get("role"))
        if mac not in self.sensors and mac not in self.plugs:
            _LOGGER.debug("Resubscribing sensor %s from measurement event", mac)
            self.sensors[mac] = role
            self._entry.runtime_data.devices.subscribe(mac)
            async_dispatcher_send(self._hass, CREATE_SENSOR_SIGNAL, mac, role)

        persisted_role = _filter_unknown(self._entry.data.get(CFG_ROLES, {}).get(mac))

        # Compute the effective role without mutating the library's dict.
        # When the device reports no role (or ROLE_UNKNOWN), fall back to the
        # persisted role so downstream entities see a stable value.
        effective_role = persisted_role if role is None else role

        if role is not None and role != persisted_role:
            self.sensors[mac] = role
            async_dispatcher_send(self._hass, ROLE_UPDATE_SIGNAL, mac, role)

        # Build the outbound message with the effective role injected.
        # We construct a new dict rather than mutating the library's original
        # so that the library can safely reuse or log the original payload.
        outbound = {**message, "role": effective_role}

        if event_type == "average_power":
            await self._vhh.process_average_power_event(outbound)
        elif event_type == "summation_energy":
            await self._vhh.process_summation_event(outbound)

        async_dispatcher_send(
            self._hass,
            f"{DATA_UPDATE_SIGNAL_PREFIX}{mac}_{event_type}",
            event_type,
            outbound,
        )

        async_dispatcher_send(
            self._hass,
            f"{DATA_UPDATE_SIGNAL_PREFIX}{mac}_role",
            "role",
            {"role": effective_role},
        )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def disconnect(self) -> None:
        """Clean up device subscriptions."""
        for mac in self.plugs:
            self._entry.runtime_data.devices.unsubscribe(mac)
        for mac in self.sensors:
            self._entry.runtime_data.devices.unsubscribe(mac)
