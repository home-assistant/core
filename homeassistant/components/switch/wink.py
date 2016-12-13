"""
Support for Wink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wink/
"""

from homeassistant.components.wink import WinkDevice
from homeassistant.helpers.entity import ToggleEntity

DEPENDENCIES = ['wink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink platform."""
    import pywink

    for switch in pywink.get_switches():
        add_devices([WinkToggleDevice(switch, hass)])
    for switch in pywink.get_powerstrip_outlets():
        add_devices([WinkToggleDevice(switch, hass)])
    for switch in pywink.get_sirens():
        add_devices([WinkToggleDevice(switch, hass)])


class WinkToggleDevice(WinkDevice, ToggleEntity):
    """Representation of a Wink toggle device."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        WinkDevice.__init__(self, wink, hass)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.set_state(True)

    def turn_off(self):
        """Turn the device off."""
        self.wink.set_state(False)
