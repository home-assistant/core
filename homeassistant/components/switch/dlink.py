"""
Support for D-link W215 smart switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.dlink/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/LinuxChristian/pyW215/archive/'
                'v0.1.1.zip#pyW215==0.1.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'D-link Smart Plug W215'
DEFAULT_PASSWORD = ''
DEFAULT_USERNAME = 'admin'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a D-Link Smart Plug."""
    from pyW215.pyW215 import SmartPlug

    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)

    add_devices([SmartPlugSwitch(SmartPlug(host, password, username), name)])


class SmartPlugSwitch(SwitchDevice):
    """Representation of a D-link Smart Plug switch."""

    def __init__(self, smartplug, name):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._name = name

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def current_power_watt(self):
        """Return the current power usage in Watt."""
        try:
            return float(self.smartplug.current_consumption)
        except ValueError:
            return None

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.smartplug.state == 'ON'

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.state = 'ON'

    def turn_off(self):
        """Turn the switch off."""
        self.smartplug.state = 'OFF'
