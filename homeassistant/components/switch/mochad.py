"""
Contains functionality to use a X10 switch over Mochad.

For more details about this platform, please refer to the documentation at
https://home.assistant.io/components/switch.mochad
"""

import logging
import threading
import voluptuous as vol

from homeassistant.components import mochad
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (CONF_NAME, CONF_DEVICES,
                                 CONF_PLATFORM, CONF_ADDRESS)
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['mochad']
_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): mochad.DOMAIN,
    CONF_DEVICES: [{
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.x10_address,
        vol.Optional(mochad.CONF_COMM_TYPE): cv.string,
    }]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up X10 switches over a mochad controller."""
    devs = config.get(CONF_DEVICES)
    crtl_lock = threading.Lock()
    add_devices([MochadSwitch(
        hass, mochad.CONTROLLER.ctrl, dev, crtl_lock) for dev in devs])
    return True


class MochadSwitch(SwitchDevice):
    """Representation of a X10 switch over Mochad."""

    def __init__(self, hass, ctrl, dev, ctrl_lock):
        """Initialize a Mochad Switch Device."""
        from pymochad import device

        self._controller = ctrl
        self._address = dev[CONF_ADDRESS]
        self._name = dev.get(CONF_NAME, 'x10_switch_dev_%s' % self._address)
        self._comm_type = dev.get(mochad.CONF_COMM_TYPE, 'pl')
        self.device = device.Device(ctrl, self._address,
                                    comm_type=self._comm_type)
        # Init with false to avoid locking HA for long on CM19A (goes from rf
        # to pl via TM751, but not other way around)
        self._state = False
        self.lock = ctrl_lock

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        with self.lock:
            try:
                self._state = True
                #Recycle socket on new command to recover mochad connection
                _LOGGER.debug("Reconnect {}:{} ".format(self._controller.server,
                                                        self._controller.port))
                self._controller.reconnect()
                self.device.send_cmd('on')
                self._controller.read_data()
            except Exception as e:
                _LOGGER.error("Error with mochad communication: {}".format(e))

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        with self.lock:
            try:
                self._state = False
                #Recycle socket on new command to recover mochad connection
                _LOGGER.debug("Reconnect {}:{} ".format(self._controller.server,
                                                         self._controller.port))
                self._controller.reconnect()
                self.device.send_cmd('off')
                self._controller.read_data()
            except Exception as e:
                _LOGGER.error("Error with mochad communication: {}".format(e))

    def _get_device_status(self):
        """Get the status of the switch from mochad."""
        status = self.device.get_status().rstrip()
        return status == 'on'

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
