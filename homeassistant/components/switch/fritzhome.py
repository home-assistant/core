"""
Support for AVM Fritz!Box fritzhome switch devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/switch.fritzhome/
"""
import logging
from homeassistant.components.fritzhome import DOMAIN
from homeassistant.components.switch import (SwitchDevice)

DEPENDENCIES = ['fritzhome']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fritzhome switch platform."""
    device_list = hass.data[DOMAIN]

    devices = []
    for device in device_list:
        if device.has_switch:
            devices.append(FritzhomeSwitch(hass, device))

    add_devices(devices)


class FritzhomeSwitch(SwitchDevice):
    """The switch class for Fritzhome switches."""

    def __init__(self, hass, device):
        """Initialize the switch."""
        self._device = device

    @property
    def available(self):
        """Return if switch is available."""
        return self._device.present

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._device.switch_state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._device.set_switch_state_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._device.set_switch_state_off()

    def update(self):
        """Get latest data and states from the device."""
        self._device.update()

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._device.power / 1000
