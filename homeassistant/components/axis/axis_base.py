"""Base classes for Axis entities."""
from axis.event_stream import AxisEvent, EventTopic

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice

TOPIC_TO_NAME = {
    EventTopic.DAY_NIGHT_VISION: "DayNight",
    EventTopic.FENCE_GUARD: "Fence Guard",
    EventTopic.LIGHT_STATUS: "Light",
    EventTopic.LOITERING_GUARD: "Loitering Guard",
    EventTopic.MOTION_DETECTION: "Motion",
    EventTopic.MOTION_DETECTION_3: "VMD3",
    EventTopic.MOTION_DETECTION_4: "VMD4",
    EventTopic.MOTION_GUARD: "Motion Guard",
    EventTopic.OBJECT_ANALYTICS: "Object Analytics",
    EventTopic.PIR: "PIR",
    EventTopic.PORT_INPUT: "Input",
    EventTopic.PORT_SUPERVISED_INPUT: "Supervised Input",
    EventTopic.PTZ_IS_MOVING: "is_moving",
    EventTopic.PTZ_ON_PRESET: "on_preset",
    EventTopic.RELAY: "Relay",
    EventTopic.SOUND_TRIGGER_LEVEL: "Sound",
}


class AxisEntityBase(Entity):
    """Base common to all Axis entities."""

    _attr_has_entity_name = True

    def __init__(self, device: AxisNetworkDevice) -> None:
        """Initialize the Axis event."""
        self.device = device

        self._attr_device_info = DeviceInfo(
            identifiers={(AXIS_DOMAIN, device.unique_id)}
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe device events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.device.signal_reachable, self.update_callback
            )
        )

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.device.available

    @callback
    def update_callback(self, no_delay=None) -> None:
        """Update the entities state."""
        self.async_write_ha_state()


class AxisEventBase(AxisEntityBase):
    """Base common to all Axis entities from event stream."""

    _attr_should_poll = False

    def __init__(self, event: AxisEvent, device: AxisNetworkDevice) -> None:
        """Initialize the Axis event."""
        super().__init__(device)
        self.event = event

        self.event_type = TOPIC_TO_NAME[event.topic_base]
        self._attr_name = f"{self.event_type} {event.id}"
        self._attr_unique_id = f"{device.unique_id}-{event.topic}-{event.id}"

        self._attr_device_class = event.group.value

    async def async_added_to_hass(self) -> None:
        """Subscribe sensors events."""
        self.event.register_callback(self.update_callback)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self.event.remove_callback(self.update_callback)
