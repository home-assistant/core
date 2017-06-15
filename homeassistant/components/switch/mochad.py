"""
Contains functionality to use a X10 switch over Mochad.

For more details about this platform, please refer to the documentation at
https://home.assistant.io/components/switch.mochad
"""

import logging

import voluptuous as vol

from homeassistant.components import mochad
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (CONF_NAME, CONF_PLATFORM)
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['mochad']
_LOGGER = logging.getLogger(__name__)

CONF_ADDRESS = 'address'
CONF_DEVICES = 'devices'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): mochad.DOMAIN,
    CONF_DEVICES: [{
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.x10_address,
        vol.Optional('comm_type'): cv.string,
    }]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up X10 switches over a mochad controller."""
    devs = config.get(CONF_DEVICES)
    add_devices([MochadSwitch(
        hass, mochad.CONTROLLER.ctrl, dev) for dev in devs])
    return True


class MochadSwitch(SwitchDevice):
    """Representation of a X10 switch over Mochad."""

    def __init__(self, hass, ctrl, dev):
        """Initialize a Mochad Switch Device."""
        from pymochad import device

        self._controller = ctrl
        self._address = dev[CONF_ADDRESS]
        self._name = dev.get(CONF_NAME, 'x10_switch_dev_%s' % self._address)
        self._comm_type = dev.get('comm_type', 'pl')
        self.device = device.Device(ctrl, self._address,
                                    comm_type=self._comm_type)
        self._state = self._get_device_status()

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self.device.send_cmd('on')
        self._controller.read_data()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self.device.send_cmd('off')
        self._controller.read_data()

    def _get_device_status(self):
        """Get the status of the switch from mochad."""
        status = self.device.get_status().rstrip()
        return status == 'on'

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
