"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.components.hdmi_cec import CecDevice, CEC_DEVICES, CEC_CLIENT
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (STATE_OFF, STATE_ON)
from homeassistant.util import convert

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Vera switches."""
    add_devices(
        CecSwitch(device, CEC_CLIENT, device) for
        device in CEC_DEVICES['switch'])


class CecSwitch(CecDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        self._state = False
        CecDevice.__init__(self, vera_device, controller)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.cecClient.ProcessCommandPowerOn()
        self._state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.cecClient.ProcessCommandPowerOn()
        self._state = STATE_OFF
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Called by the vera device callback to update state."""
        self._state = self.vera_device.is_switched_on()
