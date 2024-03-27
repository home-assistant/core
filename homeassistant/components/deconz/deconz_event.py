"""Representation of a deCONZ remote or keypad."""

from __future__ import annotations

from typing import Any

from pydeconz.models.event import EventType
from pydeconz.models.sensor.ancillary_control import (
    AncillaryControl,
    AncillaryControlAction,
)
from pydeconz.models.sensor.presence import Presence, PresenceStatePresenceEvent
from pydeconz.models.sensor.relative_rotary import RelativeRotary, RelativeRotaryEvent
from pydeconz.models.sensor.switch import Switch

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_EVENT,
    CONF_ID,
    CONF_UNIQUE_ID,
    CONF_XY,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify

from .const import ATTR_DURATION, ATTR_ROTATION, CONF_ANGLE, CONF_GESTURE, LOGGER
from .deconz_device import DeconzBase
from .hub import DeconzHub

CONF_DECONZ_EVENT = "deconz_event"
CONF_DECONZ_ALARM_EVENT = "deconz_alarm_event"
CONF_DECONZ_PRESENCE_EVENT = "deconz_presence_event"
CONF_DECONZ_RELATIVE_ROTARY_EVENT = "deconz_relative_rotary_event"

SUPPORTED_DECONZ_ALARM_EVENTS = {
    AncillaryControlAction.EMERGENCY,
    AncillaryControlAction.FIRE,
    AncillaryControlAction.INVALID_CODE,
    AncillaryControlAction.PANIC,
}
SUPPORTED_DECONZ_PRESENCE_EVENTS = {
    PresenceStatePresenceEvent.ENTER,
    PresenceStatePresenceEvent.LEAVE,
    PresenceStatePresenceEvent.ENTER_LEFT,
    PresenceStatePresenceEvent.RIGHT_LEAVE,
    PresenceStatePresenceEvent.ENTER_RIGHT,
    PresenceStatePresenceEvent.LEFT_LEAVE,
    PresenceStatePresenceEvent.APPROACHING,
    PresenceStatePresenceEvent.ABSENTING,
}
RELATIVE_ROTARY_DECONZ_TO_EVENT = {
    RelativeRotaryEvent.NEW: "new",
    RelativeRotaryEvent.REPEAT: "repeat",
}


async def async_setup_events(hub: DeconzHub) -> None:
    """Set up the deCONZ events."""

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Create DeconzEvent."""
        new_event: (
            DeconzAlarmEvent
            | DeconzEvent
            | DeconzPresenceEvent
            | DeconzRelativeRotaryEvent
        )
        sensor = hub.api.sensors[sensor_id]

        if isinstance(sensor, Switch):
            new_event = DeconzEvent(sensor, hub)

        elif isinstance(sensor, AncillaryControl):
            new_event = DeconzAlarmEvent(sensor, hub)

        elif isinstance(sensor, Presence):
            if sensor.presence_event is None:
                return
            new_event = DeconzPresenceEvent(sensor, hub)

        elif isinstance(sensor, RelativeRotary):
            new_event = DeconzRelativeRotaryEvent(sensor, hub)

        hub.hass.async_create_task(new_event.async_update_device_registry())
        hub.events.append(new_event)

    hub.register_platform_add_device_callback(
        async_add_sensor,
        hub.api.sensors.switch,
    )
    hub.register_platform_add_device_callback(
        async_add_sensor,
        hub.api.sensors.ancillary_control,
    )
    hub.register_platform_add_device_callback(
        async_add_sensor,
        hub.api.sensors.presence,
    )
    hub.register_platform_add_device_callback(
        async_add_sensor,
        hub.api.sensors.relative_rotary,
    )


@callback
def async_unload_events(hub: DeconzHub) -> None:
    """Unload all deCONZ events."""
    for event in hub.events:
        event.async_will_remove_from_hass()

    hub.events.clear()


class DeconzEventBase(DeconzBase):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(
        self,
        device: AncillaryControl | Presence | RelativeRotary | Switch,
        hub: DeconzHub,
    ) -> None:
        """Register callback that will be used for signals."""
        super().__init__(device, hub)

        self._unsubscribe = device.subscribe(self.async_update_callback)

        self.device = device
        self.device_id: str | None = None
        self.event_id = slugify(self._device.name)
        LOGGER.debug("deCONZ event created: %s", self.event_id)

    @callback
    def async_will_remove_from_hass(self) -> None:
        """Disconnect event object when removed."""
        self._unsubscribe()

    @callback
    def async_update_callback(self) -> None:
        """Fire the event if reason is that state is updated."""
        raise NotImplementedError

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        if not self.device_info:
            return

        device_registry = dr.async_get(self.hub.hass)

        entry = device_registry.async_get_or_create(
            config_entry_id=self.hub.config_entry.entry_id, **self.device_info
        )
        self.device_id = entry.id


class DeconzEvent(DeconzEventBase):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    _device: Switch

    @callback
    def async_update_callback(self) -> None:
        """Fire the event if reason is that state is updated."""
        if self.hub.ignore_state_updates or "state" not in self._device.changed_keys:
            return

        data: dict[str, Any] = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_EVENT: self._device.button_event,
        }

        if self.device_id:
            data[CONF_DEVICE_ID] = self.device_id

        if self._device.gesture is not None:
            data[CONF_GESTURE] = self._device.gesture

        if self._device.angle is not None:
            data[CONF_ANGLE] = self._device.angle

        if self._device.xy is not None:
            data[CONF_XY] = self._device.xy

        self.hub.hass.bus.async_fire(CONF_DECONZ_EVENT, data)


class DeconzAlarmEvent(DeconzEventBase):
    """Alarm control panel companion event when user interacts with a keypad."""

    _device: AncillaryControl

    @callback
    def async_update_callback(self) -> None:
        """Fire the event if reason is new action is updated."""
        if (
            self.hub.ignore_state_updates
            or "action" not in self._device.changed_keys
            or self._device.action not in SUPPORTED_DECONZ_ALARM_EVENTS
        ):
            return

        data = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_DEVICE_ID: self.device_id,
            CONF_EVENT: self._device.action.value,
        }

        self.hub.hass.bus.async_fire(CONF_DECONZ_ALARM_EVENT, data)


class DeconzPresenceEvent(DeconzEventBase):
    """Presence event."""

    _device: Presence

    @callback
    def async_update_callback(self) -> None:
        """Fire the event if reason is new action is updated."""
        if (
            self.hub.ignore_state_updates
            or "presenceevent" not in self._device.changed_keys
            or self._device.presence_event not in SUPPORTED_DECONZ_PRESENCE_EVENTS
        ):
            return

        data = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_DEVICE_ID: self.device_id,
            CONF_EVENT: self._device.presence_event.value,
        }

        self.hub.hass.bus.async_fire(CONF_DECONZ_PRESENCE_EVENT, data)


class DeconzRelativeRotaryEvent(DeconzEventBase):
    """Relative rotary event."""

    _device: RelativeRotary

    @callback
    def async_update_callback(self) -> None:
        """Fire the event if reason is new action is updated."""
        if (
            self.hub.ignore_state_updates
            or "rotaryevent" not in self._device.changed_keys
        ):
            return

        data = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_DEVICE_ID: self.device_id,
            CONF_EVENT: RELATIVE_ROTARY_DECONZ_TO_EVENT[self._device.rotary_event],
            ATTR_ROTATION: self._device.expected_rotation,
            ATTR_DURATION: self._device.expected_event_duration,
        }

        self.hub.hass.bus.async_fire(CONF_DECONZ_RELATIVE_ROTARY_EVENT, data)
