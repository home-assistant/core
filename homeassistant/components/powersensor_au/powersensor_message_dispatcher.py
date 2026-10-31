"""PowersensorMessageDispatcher routes PowersensorDevices events to HA entities.

The dispatcher is given the PowersensorZeroconfDevices instance (from
powersensor_local) which handles all plug connections, reconnections, and sensor
discovery internally.  The dispatcher's sole responsibility is to translate the
unified event stream into HA dispatcher signals that drive entity creation and
data updates.

Event routing:
  device_found  (device_type=plug)    → CREATE_PLUG_SIGNAL
  device_found  (device_type=sensor)  → CREATE_SENSOR_SIGNAL
  now_relaying_for                    → ROLE_UPDATE_SIGNAL (role hint, best-effort)
  device_lost                         → the user may now delete the device
                                        (library handles reconnection)
  average_power, summation_energy,    → DATA_UPDATE_SIGNAL_PREFIX + mac + event
    and all other measurement events    (also fed into VirtualHousehold)

Discovery lifecycle
-------------------
devices.start() registers an mDNS ServiceBrowser and returns immediately; it
does not block waiting for plugs to respond.  Plugs already present on the
network fire add_service callbacks shortly after start() returns.  The platform
(sensor.py) is set up after start() is called, so a CREATE signal can fire
before its listeners are connected.  self.plugs and self.sensors are always
updated regardless, and sensor.py seeds entities from them once it loads, so
nothing discovered in that window is lost.

There is no scan_complete event.  The browser is continuous: new plugs are
discovered as they appear and lost plugs are debounced before generating a
device_lost event.

now_relaying_for role hint
--------------------------
device_found carries no role.  The library documents that role information is
not reliably available at that point because of hardware limitations, so it
leaves the field out.  relay_now_relaying_for=True is the library's option for
callers that want the relayed message as well: it forwards the raw
now_relaying_for event to the callback immediately after the synthesised
device_found for the same sensor.  That event carries the role field straight
from the wire, which lets us seed the role in HA without waiting for the first
measurement event to arrive.

The role is treated as a hint: present on most devices, absent on some very old
hardware, and occasionally None/unknown on newer devices.  When absent or None
the existing persisted role fallback in _handle_device_found takes over, and
any subsequent measurement event with a concrete role will correct it via the
normal ROLE_UPDATE_SIGNAL path.

Expiry recovery
---------------
The library removes a device that disappears from the network or stays silent
for too long (e.g. a plug that was temporarily offline), and fires device_found
again if it comes back.  Its subscription is removed along with it: the
library's subscribe() documents that subscriptions do not survive a device
disappearing, and that callers who still want its events must re-subscribe on
device_found.  When that happens, the MAC is already in self.plugs /
self.sensors (entities already exist), so we skip the CREATE signal to avoid
duplicates — but we MUST still call devices.subscribe(mac).  Without it the
library delivers none of the device's events and its entities appear
permanently dead.
"""

import logging
from typing import Any

from powersensor_local import VirtualHousehold
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    DEVICE_REMOVED_SIGNAL,
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
        devices: PowersensorZeroconfDevices,
    ) -> None:
        """Initialize the dispatcher.

        Args:
            hass: The Home Assistant instance.
            entry: The config entry this dispatcher belongs to.
            vhh: The VirtualHousehold calculation engine.
            devices: The library instance whose events this dispatcher routes.
        """
        self._hass = hass
        self._entry = entry
        self._vhh = vhh
        self._devices = devices

        # Tracks known devices.  The library announces a device only once while
        # it holds it, but announces it again after removing it, so this is what
        # stops a returning device from getting duplicate entities (see
        # _handle_device_found).  A device leaves these only when the user
        # deletes it (see forget), because its entities go with it.
        self.plugs: set[str] = set()
        self.sensors: dict[str, str | None] = {}
        # Devices the library currently holds: from device_found until
        # device_lost, which it sends once a device has been silent for a few
        # minutes or a plug has left the network.
        self._present: set[str] = set()

    def is_present(self, mac: str) -> bool:
        """Return whether the device is currently on the network."""
        return mac in self._present

    def forget(self, mac: str) -> None:
        """Forget a device the user has deleted, so it is set up anew if it returns."""
        self.plugs.discard(mac)
        self.sensors.pop(mac, None)
        async_dispatcher_send(self._hass, DEVICE_REMOVED_SIGNAL, mac)

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
        sensors (found when a plug relays a now_relaying_for message, from
        which the library synthesises the device_found).

        Note: device_found carries no role.  The library documents that role
        information is not reliably available at that point because of
        hardware limitations.  The role arrives separately via the forwarded
        now_relaying_for event
        (handled by _handle_now_relaying_for), which fires immediately after
        device_found for the same sensor in the same event sequence.  As a
        belt-and-braces fallback we also check the persisted role so that
        role-gated entities are created correctly on reload/reboot even if the
        now_relaying_for event somehow arrives before the entity platform is
        ready.

        Re-subscribe after expiry: if the MAC is already known (i.e. we have
        entities for it), the library removed the device after it disappeared
        or went silent, and is now announcing it again.  We skip the CREATE
        signal (no duplicate entities) but still call devices.subscribe(mac).
        The library drops a device's subscription when it removes the device,
        and its subscribe() documentation asks callers to re-subscribe on
        device_found; without this call none of the device's subsequent events
        would be delivered.
        """
        mac = event.get("mac")
        device_type = event.get("device_type")
        if mac is None:
            return
        self._present.add(mac)

        if device_type == "plug":
            if mac not in self.plugs:
                _LOGGER.debug("New plug discovered: %s", mac)
                self.plugs.add(mac)
                self._devices.subscribe(mac)
                async_dispatcher_send(self._hass, CREATE_PLUG_SIGNAL, mac)
            else:
                # MAC already known — the library removed the device and is
                # announcing it again.  Its subscription went with it, so
                # re-subscribe for events to flow again.
                _LOGGER.debug(
                    "Plug re-discovered after expiry, re-subscribing: %s", mac
                )
                self._devices.subscribe(mac)

        elif device_type == "sensor":
            if mac not in self.sensors:
                # Role is not available in device_found for sensors; it arrives
                # via now_relaying_for which fires immediately after.  Fall back
                # to the persisted role so role-gated entities are created on
                # reload without waiting for the wire.
                role = _filter_unknown(self._entry.data[CFG_ROLES].get(mac))
                _LOGGER.debug("New sensor discovered: %s role=%s", mac, role)
                self.sensors[mac] = role
                self._devices.subscribe(mac)
                async_dispatcher_send(self._hass, CREATE_SENSOR_SIGNAL, mac, role)
            else:
                # MAC already known — re-subscribe after expiry (same as plug case).
                _LOGGER.debug(
                    "Sensor re-discovered after expiry, re-subscribing: %s", mac
                )
                self._devices.subscribe(mac)

    def _handle_now_relaying_for(self, event: dict[str, Any]) -> None:
        """Handle the forwarded now_relaying_for event as a role hint.

        This fires immediately after device_found for the same sensor MAC, so
        the sensor is already in self.sensors by the time we arrive here.  We
        use the wire role to refine what device_found just seeded (which was
        the persisted role or None).

        The library creates this event for the first message from each MAC
        that a plug passes on, other than the plug's own.  A plug passes on
        only its own readings and those of the sensors it relays: it cannot
        relay another plug.  So the event always describes a sensor, and the
        device_type check below only makes sure nothing else could ever be
        listed among the sensors or have its role saved.

        The role is treated as best-effort:
          - Present on most devices → record it in self.sensors, save it, and
            send ROLE_UPDATE_SIGNAL to update role-gated entities.
          - Absent (None) on old hardware or occasionally on newer devices →
            leave whatever device_found already seeded; the first measurement
            event will correct it via the normal ROLE_UPDATE_SIGNAL path.

        self.sensors and the saved role are written here, not by the signal's
        receiver, so they are correct even when the sensor platform has not
        connected its listeners yet (see "Discovery lifecycle" above).
        """
        mac = event.get("mac")
        if mac is None or event.get("device_type") != "sensor":
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
        self.sensors[mac] = wire_role
        self._save_role(mac, wire_role)
        # ROLE_UPDATE_SIGNAL updates role-gated entities and renames the device
        # via sensor.py's handle_role_update callback.
        async_dispatcher_send(self._hass, ROLE_UPDATE_SIGNAL, mac, wire_role)

    def _save_role(self, mac: str, role: str) -> None:
        """Save a role the device reported, as the fallback for its messages.

        Saved here rather than by the platform, which only listens once it has
        loaded: discovery starts before that, and a role learned in between
        would otherwise never be saved.
        """
        roles = self._entry.data[CFG_ROLES]
        _LOGGER.debug("Saving role for %s: %s → %s", mac, roles.get(mac), role)
        self._hass.config_entries.async_update_entry(
            self._entry, data={**self._entry.data, CFG_ROLES: {**roles, mac: role}}
        )

    def _handle_device_lost(self, event: dict[str, Any]) -> None:
        """Handle a plug or sensor going offline.

        The library manages reconnection internally, so we don't remove
        entities.  Entities naturally become unavailable when their data
        update timeout fires.  From here on the user may delete the device.
        """
        mac = event.get("mac")
        if mac is None:
            return
        self._present.discard(mac)
        _LOGGER.debug("Device lost: %s", mac)

    async def _handle_measurement(
        self, event_type: str, message: dict[str, Any]
    ) -> None:
        """Route a measurement event to the appropriate HA signals."""
        mac = message.get("mac")
        if mac is None:
            return

        role = _filter_unknown(message.get("role"))
        persisted_role = _filter_unknown(self._entry.data[CFG_ROLES].get(mac))

        # Compute the effective role without mutating the library's dict.
        # When the device reports no role (or ROLE_UNKNOWN), fall back to the
        # persisted role so downstream entities see a stable value.  This is
        # also how a role assigned in the reconfigure flow takes effect for a
        # sensor that never reports one: VirtualHousehold only counts events
        # whose role is house-net or solar.
        effective_role = persisted_role if role is None else role

        if role is not None and role != persisted_role:
            # Plugs report a role too, and saving it is deliberate: plug
            # messages without a role fall back to it.  But a plug must not end
            # up listed among the sensors.
            if mac in self.sensors:
                self.sensors[mac] = role
            self._save_role(mac, role)
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

        # Sent with every measurement, not only when the role changes: like any
        # device entity, device_role goes unavailable without an update within
        # its timeout, so this signal also keeps it available.  An unchanged
        # role only restarts that timeout; device_role isn't written again.
        async_dispatcher_send(
            self._hass,
            f"{DATA_UPDATE_SIGNAL_PREFIX}{mac}_role",
            "role",
            {"role": effective_role},
        )

    async def disconnect(self) -> None:
        """Clean up device subscriptions."""
        for mac in self.plugs:
            self._devices.unsubscribe(mac)
        for mac in self.sensors:
            self._devices.unsubscribe(mac)
