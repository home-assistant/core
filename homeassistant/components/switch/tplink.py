"""Support for TPLink HS100/HS110 smart switch.

It is able to monitor current switch status, as well as turn on and off the switch. 

"""

import logging
import socket
import codecs

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_HOST, CONF_NAME)

# constants
DEVICE_DEFAULT_NAME = 'HS100'
REQUIREMENTS = ['http://github.com/gadgetreactor/pyHS100/archive/'
                '27dd078e57628e76a1de89cc9d81b703f8e846d1'
                '#pyHS100==0.1.0']

# setup logger
_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    import pyHS100
    """Setup the TPLink platform in configuration.yaml."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME, DEVICE_DEFAULT_NAME)

    add_devices_callback([SmartPlugSwitch(pyHS100.SmartPlug(host),
                                          name)])

class SmartPlugSwitch(SwitchDevice):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(self, smartplug, name):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._name = name

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

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
