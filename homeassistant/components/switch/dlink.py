"""
Support for D-link W215 smart switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.dlink/
"""
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import validate_config

# constants
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = ''
DEVICE_DEFAULT_NAME = 'D-link Smart Plug W215'
REQUIREMENTS = ['https://github.com/LinuxChristian/pyW215/archive/'
                'v0.1.1.zip#pyW215==0.1.1']

# setup logger
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return D-Link Smart Plugs."""
    from pyW215.pyW215 import SmartPlug

    # check for required values in configuration file
    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_HOST]},
                           _LOGGER):
        return False

    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME, DEFAULT_USERNAME)
    password = str(config.get(CONF_PASSWORD, DEFAULT_PASSWORD))
    name = config.get(CONF_NAME, DEVICE_DEFAULT_NAME)

    add_devices_callback([SmartPlugSwitch(SmartPlug(host,
                                                    password,
                                                    username),
                                          name)])


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
