"""Entity to track connections to stream API."""
import asyncio
import logging

from homeassistant.helpers.entity import Entity


class StreamHandler(logging.Handler):
    """Check log messages for stream connect/disconnect."""

    def __init__(self, entity):
        """Initialize handler."""
        super().__init__()
        self.entity = entity
        self.count = 0

    def handle(self, record):
        """Handle a log message."""
        if not record.msg.startswith('STREAM'):
            return

        if record.msg.endswith('ATTACHED'):
            self.entity.count += 1
        elif record.msg.endswith('RESPONSE CLOSED'):
            self.entity.count -= 1

        self.entity.schedule_update_ha_state()


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the logger for filters."""
    entity = APICount()

    logging.getLogger('homeassistant.components.api').addHandler(
        StreamHandler(entity))

    yield from async_add_devices([entity])


class APICount(Entity):
    """Entity to represent how many people are connected to stream API."""

    def __init__(self):
        """Initialize the API count."""
        self.count = 0

    @property
    def name(self):
        """Return name of entity."""
        return "Connected clients"

    @property
    def state(self):
        """Return current API count."""
        return self.count

    @property
    def unit_of_measurement(self):
        """Unit of measurement."""
        return "clients"
