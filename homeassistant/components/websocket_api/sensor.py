"""Entity to track connections to websocket API."""

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import SIGNAL_WEBSOCKET_CONNECTED, SIGNAL_WEBSOCKET_DISCONNECTED


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the API streams platform."""
    entity = APICount()

    # pylint: disable=protected-access
    hass.helpers.dispatcher.async_dispatcher_connect(
        SIGNAL_WEBSOCKET_CONNECTED, entity._increment)
    hass.helpers.dispatcher.async_dispatcher_connect(
        SIGNAL_WEBSOCKET_DISCONNECTED, entity._decrement)

    async_add_entities([entity])


class APICount(Entity):
    """Entity to represent how many people are connected to the stream API."""

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
        """Return the unit of measurement."""
        return "clients"

    @callback
    def _increment(self):
        self.count += 1
        self.async_schedule_update_ha_state()

    @callback
    def _decrement(self):
        self.count -= 1
        self.async_schedule_update_ha_state()
