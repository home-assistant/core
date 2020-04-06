"""Base classes for Axis entities."""

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as AXIS_DOMAIN


class AxisEntityBase(Entity):
    """Base common to all Axis entities."""

    def __init__(self, device):
        """Initialize the Axis event."""
        self.device = device

    async def async_added_to_hass(self):
        """Subscribe device events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.device.event_reachable, self.update_callback
            )
        )

    @property
    def available(self):
        """Return True if device is available."""
        return self.device.available

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {"identifiers": {(AXIS_DOMAIN, self.device.serial)}}

    @callback
    def update_callback(self, no_delay=None):
        """Update the entities state."""
        self.async_write_ha_state()


class AxisEventBase(AxisEntityBase):
    """Base common to all Axis entities from event stream."""

    def __init__(self, event, device):
        """Initialize the Axis event."""
        super().__init__(device)
        self.event = event

    async def async_added_to_hass(self) -> None:
        """Subscribe sensors events."""
        self.event.register_callback(self.update_callback)

        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self.event.remove_callback(self.update_callback)

        await super().async_will_remove_from_hass()

    @property
    def device_class(self):
        """Return the class of the event."""
        return self.event.CLASS

    @property
    def name(self):
        """Return the name of the event."""
        return f"{self.device.name} {self.event.TYPE} {self.event.id}"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return f"{self.device.serial}-{self.event.topic}-{self.event.id}"
