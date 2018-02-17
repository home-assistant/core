"""
Support for AVM Fritz!Box smarthome switch devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/switch.fritzbox/
"""
import logging

import requests

from homeassistant.components.fritzhome import DOMAIN as FRITZEBOX_DOMAIN
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['fritzbox']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fritzbox switch platform."""
    fritz = hass.data[FRITZBOX_DOMAIN]
    device_list = fritz.get_devices()

    devices = []
    for device in device_list:
        if device.has_switch:
            devices.append(FritzboxSwitch(device, fritz))

    add_devices(devices)


class FritzboxSwitch(SwitchDevice):
    """The switch class for Fritzbox switches."""

    def __init__(self, device, fritz):
        """Initialize the switch."""
        self._device = device
        self._fritz = fritz

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
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            _LOGGER.warning("Fritzhome connection error: %s", ex)
            self._fritz.login()

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._device.power / 1000
