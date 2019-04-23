"""Base class for Axis event entities."""

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as AXIS_DOMAIN


class AxisEventBase(Entity):
    """Representation of an Axis event."""

    def __init__(self, event, device):
        """Initialize the Axis event."""
        self.event = event
        self.device = device
        self.unsub_dispatcher = None

    async def async_added_to_hass(self):
        """Subscribe sensors events."""
        self.event.register_callback(self.update_callback)
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, self.device.event_reachable, self.update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self.event.remove_callback(self.update_callback)
        self.unsub_dispatcher()

    @callback
    def update_callback(self, no_delay=None):
        """Update the entities state."""
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the event."""
        return '{} {} {}'.format(
            self.device.name, self.event.TYPE, self.event.id)

    @property
    def device_class(self):
        """Return the class of the event."""
        return self.event.CLASS

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return '{}-{}-{}'.format(
            self.device.serial, self.event.topic, self.event.id)

    def available(self):
        """Return True if device is available."""
        return self.device.available

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            'identifiers': {(AXIS_DOMAIN, self.device.serial)}
        }
