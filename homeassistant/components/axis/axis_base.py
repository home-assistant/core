"""Base classes for Axis entities."""
from axis.event_stream import AxisEvent

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice


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

        self._attr_name = f"{event.TYPE} {event.id}"
        self._attr_unique_id = f"{device.unique_id}-{event.topic}-{event.id}"

        self._attr_device_class = event.CLASS

    async def async_added_to_hass(self) -> None:
        """Subscribe sensors events."""
        self.event.register_callback(self.update_callback)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self.event.remove_callback(self.update_callback)
