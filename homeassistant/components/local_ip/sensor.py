"""Sensor platform for local_ip."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.util import get_local_ip

from .const import DOMAIN, SENSOR


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the platform from config_entry."""
    name = config_entry.data.get(CONF_NAME) or DOMAIN
    async_add_entities([IPSensor(name)], True)


class IPSensor(SensorEntity):
    """A simple sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
