"""Entity to track connections to websocket API."""

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import (
    DATA_CONNECTIONS,
    SIGNAL_WEBSOCKET_CONNECTED,
    SIGNAL_WEBSOCKET_DISCONNECTED,
)

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the API streams platform."""
    entity = APICount()

    async_add_entities([entity])


class APICount(Entity):
    """Entity to represent how many people are connected to the stream API."""

    def __init__(self):
        """Initialize the API count."""
        self.count = 0

    async def async_added_to_hass(self):
        """Added to hass."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_WEBSOCKET_CONNECTED, self._update_count
            )
        )
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_WEBSOCKET_DISCONNECTED, self._update_count
            )
        )

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
    def _update_count(self):
        self.count = self.hass.data.get(DATA_CONNECTIONS, 0)
        self.async_write_ha_state()
