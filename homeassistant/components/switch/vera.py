"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.util import convert
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    STATE_OFF, STATE_ON)
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return Vera switches."""
    add_devices_callback(
        VeraSwitch(device, VERA_CONTROLLER) for
        device in VERA_DEVICES['switch'])


class VeraSwitch(VeraDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.vera_device.switch_on()
        self._state = STATE_ON
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.vera_device.switch_off()
        self._state = STATE_OFF
        self.update_ha_state()

    @property
    def current_power_mwh(self):
        """Current power usage in mWh."""
        power = self.vera_device.power
        if power:
            return convert(power, float, 0.0) * 1000

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Called by the vera device callback to update state."""
        self._state = self.vera_device.is_switched_on()
