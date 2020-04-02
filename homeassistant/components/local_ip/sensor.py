"""Sensor platform for local_ip."""

from homeassistant.helpers.entity import Entity
from homeassistant.util import get_local_ip

from .const import DOMAIN, SENSOR


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the platform from config_entry."""
    async_add_entities([IPSensor()], True)


class IPSensor(Entity):
    """A simple sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return DOMAIN

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return SENSOR

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:ip"

    def update(self):
        """Fetch new state data for the sensor."""
        self._state = get_local_ip()
