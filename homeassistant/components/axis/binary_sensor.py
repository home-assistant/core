"""Support for Axis binary sensors."""
from __future__ import annotations

from datetime import timedelta

from axis.models.event import Event, EventGroup, EventOperation, EventTopic

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .axis_base import AxisEventBase
from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice

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


class AxisBinarySensor(AxisEventBase, BinarySensorEntity):
    """Representation of a binary Axis event."""

    def __init__(self, event: Event, device: AxisNetworkDevice) -> None:
        """Initialize the Axis binary sensor."""
        super().__init__(event, device)
        self.cancel_scheduled_update = None

        self._attr_device_class = DEVICE_CLASS.get(self.event.group)
        self._attr_is_on = event.is_tripped

    @callback
    def update_callback(self, no_delay=False):
        """Update the sensor's state, if needed.

        Parameter no_delay is True when device_event_reachable is sent.
        """
        self._attr_is_on = self.event.is_tripped

        @callback
        def scheduled_update(now):
            """Timer callback for sensor update."""
            self.cancel_scheduled_update = None
            self.async_write_ha_state()

        if self.cancel_scheduled_update is not None:
            self.cancel_scheduled_update()
            self.cancel_scheduled_update = None

        if self.is_on or self.device.option_trigger_time == 0 or no_delay:
            self.async_write_ha_state()
            return

        self.cancel_scheduled_update = async_track_point_in_utc_time(
            self.hass,
            scheduled_update,
            utcnow() + timedelta(seconds=self.device.option_trigger_time),
        )

    @property
    def name(self) -> str | None:
        """Return the name of the event."""
        if (
            self.event.group == EventGroup.INPUT
            and self.event.id in self.device.api.vapix.ports
            and self.device.api.vapix.ports[self.event.id].name
        ):
            return self.device.api.vapix.ports[self.event.id].name

        if self.event.group == EventGroup.MOTION:

            for event_topic, event_data in (
                (EventTopic.FENCE_GUARD, self.device.api.vapix.fence_guard),
                (EventTopic.LOITERING_GUARD, self.device.api.vapix.loitering_guard),
                (EventTopic.MOTION_GUARD, self.device.api.vapix.motion_guard),
                (EventTopic.OBJECT_ANALYTICS, self.device.api.vapix.object_analytics),
                (EventTopic.MOTION_DETECTION_4, self.device.api.vapix.vmd4),
            ):

                if (
                    self.event.topic_base == event_topic
                    and event_data
                    and self.event.id in event_data
                ):
                    return f"{self.event_type} {event_data[self.event.id].name}"

        return self._attr_name
