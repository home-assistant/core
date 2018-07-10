"""
Support for Tahoma Switch - those are push buttons for garage door etc.

Those buttons are implemented as switches that are never on. They only
receive the turn_on action, perform the relay click, and stay in OFF state

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tahoma/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.tahoma import (
    DOMAIN as TAHOMA_DOMAIN, TahomaDevice)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tahoma switches."""
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for switch in hass.data[TAHOMA_DOMAIN]['devices']['switch']:
        devices.append(TahomaSwitch(switch, controller))
    add_devices(devices, True)


class TahomaSwitch(TahomaDevice, SwitchDevice):
    """Representation a Tahoma Switch."""

    @property
    def device_class(self):
        """Return the class of the device."""
        if self.tahoma_device.type == 'rts:GarageDoor4TRTSComponent':
            return 'garage'
        return None

    def turn_on(self, **kwargs):
        """Send the on command."""
        self.toggle()

    def toggle(self, **kwargs):
        """Click the switch."""
        self.apply_action('cycle')

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        return False
