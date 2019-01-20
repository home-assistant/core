"""
A component to connect to Owlet baby monitor

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/owlet/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyowlet==1.0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'owlet'

SENSOR_TYPES = [
    'oxygen_level',
    'heart_rate',
    'base_station_on',
    'movement'
]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup owlet component"""
    from pyowlet.PyOwlet import PyOwlet

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    name = config[DOMAIN].get(CONF_NAME)

    device = PyOwlet(username, password)

    device.update_properties()

    if not name:
        name = '{}\'s Owlet'.format(device.baby_name)

    hass.data[DOMAIN] = OwletDevice(device, name, SENSOR_TYPES)

    return True


class OwletDevice():
    """Configured Owlet device"""

    def __init__(self, device, name, monitor):
        """Initialize device."""
        self._name = name
        self._monitor = monitor
        self._device = device

    @property
    def name(self):
        """Get the name of the device."""
        return self._name

    @property
    def monitor(self):
        """Get monitored conditions."""
        return self._monitor

    @property
    def device(self):
        """Get device."""
        return self._device
