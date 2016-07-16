"""
Support for TPLink HS100/HS110 smart switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tplink/
"""
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_HOST, CONF_NAME)

# constants
DEVICE_DEFAULT_NAME = 'HS100'
REQUIREMENTS = ['https://github.com/gadgetreactor/pyHS100/archive/'
                'master.zip#pyHS100==0.1.2']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the TPLink switch platform."""
    from pyHS100.pyHS100 import SmartPlug
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME, DEVICE_DEFAULT_NAME)

    add_devices_callback([SmartPlugSwitch(SmartPlug(host),
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
