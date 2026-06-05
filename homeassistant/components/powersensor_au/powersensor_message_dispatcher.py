"""PowersensorMessageDispatcher routes PowersensorDevices events to HA entities.

The dispatcher owns a single PowersensorZeroconfDevices instance (from
powersensor_local) which handles all plug connections, reconnections, and sensor
discovery internally.  The dispatcher's sole responsibility is to translate the
unified event stream into HA dispatcher signals that drive entity creation and
data updates.

Event routing:
  device_found  (device_type=plug)    → CREATE_PLUG_SIGNAL
  device_found  (device_type=sensor)  → CREATE_SENSOR_SIGNAL
  now_relaying_for                    → ROLE_UPDATE_SIGNAL (role hint, best-effort)
  device_lost                         → logged (library handles reconnection)
  average_power, summation_energy,    → DATA_UPDATE_SIGNAL_PREFIX + mac + event
    and all other measurement events    (also fed into VirtualHousehold)

Discovery lifecycle
-------------------
devices.start() registers an mDNS ServiceBrowser and returns immediately; it
does not block waiting for plugs to respond.  Plugs already present on the
network fire add_service callbacks shortly after start() returns.  The platform
(sensor.py) is set up before start() is called, so its signal listeners are
always ready when those events arrive.

Unlike the legacy UDP scan there is no scan_complete event.  The browser is
continuous: new plugs are discovered as they appear and lost plugs are
debounced before generating a device_lost event.

now_relaying_for role hint
--------------------------
When relay_now_relaying_for=True is passed to PowersensorZeroconfDevices, the
library forwards the raw now_relaying_for event to the callback immediately
after synthesising the device_found event for the sensor.  This event carries
the role field directly from the wire message, which lets us seed the role in
HA without waiting for the first measurement event to arrive.

The role is treated as a hint: present on most devices, absent on some very old
hardware, and occasionally None/unknown on newer devices.  When absent or None
the existing persisted role fallback in _handle_device_found takes over, and
any subsequent measurement event with a concrete role will correct it via the
normal ROLE_UPDATE_SIGNAL path.

Expiry recovery
---------------
The library's expiry timer removes devices that have been silent for too long
(e.g. a plug that was temporarily offline).  When the plug re-announces via
mDNS, the library re-adds the device and fires device_found again.  When that
happens, the MAC is already in self.plugs / self.sensors (entities already
exist), so we skip the CREATE signal to avoid duplicates — but we MUST still
call devices.subscribe(mac) because the re-added _Device object starts with
subscribed=False.  Without this re-subscribe, _emit_if_subscribed silently
drops all events and the sensors appear permanently dead.
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
    """Routes PowersensorZeroconfDevices events to HA entity lifecycle signals."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vhh: VirtualHousehold,
    ) -> None:
        """Initialize the dispatcher.

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
    # PowersensorZeroconfDevices unified event callback
    # ------------------------------------------------------------------

    async def on_device_event(self, event: dict[str, Any]) -> None:
        """Handle all events from the PowersensorZeroconfDevices unified stream.

        This is the single callback passed to PowersensorZeroconfDevices.start().
        """
        event_type = event.get("event")

        match event_type:
            case "device_found":
                await self._handle_device_found(event)
            case "now_relaying_for":
                self._handle_now_relaying_for(event)
            case "device_lost":
                self._handle_device_lost(event)
            case _:
                if event_type is not None:
                    await self._handle_measurement(event_type, event)

    async def _handle_device_found(self, event: dict[str, Any]) -> None:
        """Handle a newly discovered plug or sensor.

        The library emits device_found for both plugs (found via mDNS) and
        sensors (found when a plug relays a now_relaying_for message, which
        the library converts to a device_found internally).

        Note: the library does not populate role in the device_found event for
        sensors — it is lost in the now_relaying_for → _add_device conversion.
        The role arrives separately via the forwarded now_relaying_for event
        (handled by _handle_now_relaying_for), which fires immediately after
        device_found for the same sensor in the same event sequence.  As a
        belt-and-braces fallback we also check the persisted role so that
        role-gated entities are created correctly on reload/reboot even if the
        now_relaying_for event somehow arrives before the entity platform is
        ready.

        Re-subscribe after expiry: if the MAC is already known (i.e. we have
        entities for it) but the library re-fired device_found because its
        internal _Device was removed by the expiry timer and then re-added by
        a new mDNS announcement, we skip the CREATE signal (no duplicate
        entities) but still call devices.subscribe(mac).  The library creates
        a fresh _Device with subscribed=False, so without this call
        _emit_if_subscribed would silently discard all subsequent events.
        """
        mac = event.get("mac")
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
                # re-added by a fresh mDNS announcement.  Re-subscribe so
                # events flow again.
                _LOGGER.debug(
                    "Plug re-discovered after expiry, re-subscribing: %s", mac
                )
                self._entry.runtime_data.devices.subscribe(mac)

        elif device_type == "sensor":
            if mac not in self.sensors:
                # Role is not available in device_found for sensors; it arrives
                # via now_relaying_for which fires immediately after.  Fall back
                # to the persisted role so role-gated entities are created on
                # reload without waiting for the wire.
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

    def _handle_now_relaying_for(self, event: dict[str, Any]) -> None:
        """Handle the forwarded now_relaying_for event as a role hint.

        This fires immediately after device_found for the same sensor MAC, so
        the sensor is already in self.sensors by the time we arrive here.  We
        use the wire role to refine what device_found just seeded (which was
        the persisted role or None).

        The role is treated as best-effort:
          - Present on most devices → send ROLE_UPDATE_SIGNAL to update
            role-gated entities and persist the value.
          - Absent (None) on old hardware or occasionally on newer devices →
            leave whatever device_found already seeded; the first measurement
            event will correct it via the normal ROLE_UPDATE_SIGNAL path.
        """
        mac = event.get("mac")
        if mac is None:
            return

        wire_role = _filter_unknown(event.get("role"))
        if wire_role is None:
            # No usable role on this announcement — leave the persisted value
            # in place and let the measurement path sort it out.
            _LOGGER.debug(
                "now_relaying_for for %s: no role on wire, deferring to measurement path",
                mac,
            )
            return

        current_role = self.sensors.get(mac)
        if wire_role == current_role:
            return  # already up to date

        _LOGGER.debug(
            "now_relaying_for role hint for %s: %s → %s",
            mac,
            current_role,
            wire_role,
        )
        # ROLE_UPDATE_SIGNAL updates role-gated entities, persists the role,
        # and keeps dispatcher.sensors in sync — all via sensor.py's
        # handle_role_update callback.
        async_dispatcher_send(self._hass, ROLE_UPDATE_SIGNAL, mac, wire_role)

    def _handle_device_lost(self, event: dict[str, Any]) -> None:
        """Handle a plug or sensor going offline.

        The library manages reconnection internally, so we don't remove
        entities.  Entities naturally become unavailable when their data
        update timeout fires.
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
