"""Support for Axis binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from axis.models.event import Event, EventGroup, EventOperation, EventTopic

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice
from .entity import AxisEventEntity

DEVICE_CLASS = {
    EventGroup.INPUT: BinarySensorDeviceClass.CONNECTIVITY,
    EventGroup.LIGHT: BinarySensorDeviceClass.LIGHT,
    EventGroup.MOTION: BinarySensorDeviceClass.MOTION,
    EventGroup.SOUND: BinarySensorDeviceClass.SOUND,
}

EVENT_TOPICS = (
    EventTopic.DAY_NIGHT_VISION,
    EventTopic.FENCE_GUARD,
    EventTopic.LOITERING_GUARD,
    EventTopic.MOTION_DETECTION,
    EventTopic.MOTION_DETECTION_3,
    EventTopic.MOTION_DETECTION_4,
    EventTopic.MOTION_GUARD,
    EventTopic.OBJECT_ANALYTICS,
    EventTopic.PIR,
    EventTopic.PORT_INPUT,
    EventTopic.PORT_SUPERVISED_INPUT,
    EventTopic.SOUND_TRIGGER_LEVEL,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Axis binary sensor."""
    device: AxisNetworkDevice = hass.data[AXIS_DOMAIN][config_entry.entry_id]

    @callback
    def async_create_entity(event: Event) -> None:
        """Create Axis binary sensor entity."""
        async_add_entities([AxisBinarySensor(event, device)])

    device.api.event.subscribe(
        async_create_entity,
        topic_filter=EVENT_TOPICS,
        operation_filter=EventOperation.INITIALIZED,
    )


class AxisBinarySensor(AxisEventEntity, BinarySensorEntity):
    """Representation of a binary Axis event."""

    def __init__(self, event: Event, device: AxisNetworkDevice) -> None:
        """Initialize the Axis binary sensor."""
        super().__init__(event, device)
        self.cancel_scheduled_update: Callable[[], None] | None = None

        self._attr_device_class = DEVICE_CLASS.get(event.group)
        self._attr_is_on = event.is_tripped

        self._set_name(event)

    @callback
    def async_event_callback(self, event: Event) -> None:
        """Update the sensor's state, if needed."""
        self._attr_is_on = event.is_tripped

        @callback
        def scheduled_update(now):
            """Timer callback for sensor update."""
            self.cancel_scheduled_update = None
            self.async_write_ha_state()

        if self.cancel_scheduled_update is not None:
            self.cancel_scheduled_update()
            self.cancel_scheduled_update = None

        if self.is_on or self.device.option_trigger_time == 0:
            self.async_write_ha_state()
            return

        self.cancel_scheduled_update = async_call_later(
            self.hass,
            timedelta(seconds=self.device.option_trigger_time),
            scheduled_update,
        )

    @callback
    def _set_name(self, event: Event) -> None:
        """Set binary sensor name."""
        if (
            event.group == EventGroup.INPUT
            and event.id in self.device.api.vapix.ports
            and self.device.api.vapix.ports[event.id].name
        ):
            self._attr_name = self.device.api.vapix.ports[event.id].name

        elif event.group == EventGroup.MOTION:
            for event_topic, event_data in (
                (EventTopic.FENCE_GUARD, self.device.api.vapix.fence_guard),
                (EventTopic.LOITERING_GUARD, self.device.api.vapix.loitering_guard),
                (EventTopic.MOTION_GUARD, self.device.api.vapix.motion_guard),
                (EventTopic.OBJECT_ANALYTICS, self.device.api.vapix.object_analytics),
                (EventTopic.MOTION_DETECTION_4, self.device.api.vapix.vmd4),
            ):
                if (
                    event.topic_base == event_topic
                    and event_data
                    and event.id in event_data
                ):
                    self._attr_name = f"{self._event_type} {event_data[event.id].name}"
                    break
