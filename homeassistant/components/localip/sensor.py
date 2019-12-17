"""Sensor platform for localip."""
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util import get_local_ip

from . import DOMAIN


def setup_platform(hass: HomeAssistant, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    name = hass.data[DOMAIN][CONF_NAME]
    local_ip = get_local_ip()
    add_entities([IPSensor(name, local_ip)])


class IPSensor(Entity):
    """A simple sensor."""

    def __init__(self, name, ip):
        """Initialize the sensor."""
        self._state = ip
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch new state data for the sensor."""
        self._state = get_local_ip()
