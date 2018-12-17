"""
Contains functionality to use a X10 switch over Mochad.

For more details about this platform, please refer to the documentation at
https://home.assistant.io/components/switch.mochad
"""

import logging

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up X10 switches over a mochad controller."""
    devs = config.get(CONF_DEVICES)
    controller = hass.data[mochad.DOMAIN]
    add_entities([MochadSwitch(
        hass, controller.ctrl_recv, dev) for dev in devs])
    return True


class MochadSwitch(SwitchDevice):
    """Representation of a X10 switch over Mochad."""

    def __init__(self, hass, ctrl, dev):
        """Initialize a Mochad Switch Device."""
        self._controller = ctrl
        self._address = dev[CONF_ADDRESS]
        self._name = dev.get(CONF_NAME, 'x10_switch_dev_%s' % self._address)
        self._comm_type = dev.get(mochad.CONF_COMM_TYPE, 'pl')
        self._state = self._get_device_status()

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def send_cmd(self, cmd):
        """Send cmd to pymochad controller."""
        from pymochad import device

        if self._controller.ctrl and self._controller.connect_event.wait():
            switch = device.Device(self._controller.ctrl, self._address,
                                   comm_type=self._comm_type)
            switch.send_cmd(cmd)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        from pymochad.exceptions import MochadException

        self._controller.connect_event.wait()
        _LOGGER.debug("Reconnect %s:%s", self._controller.ctrl.server,
                      self._controller.ctrl.port)
        with mochad.REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.ctrl.reconnect()

                self.send_cmd('on')
                # No read data on CM19A which is rf only
                if self._comm_type == 'pl':
                    self._controller.ctrl.read_data()
                self._state = True
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        from pymochad.exceptions import MochadException

        self._controller.connect_event.wait()
        _LOGGER.debug("Reconnect %s:%s", self._controller.ctrl.server,
                      self._controller.ctrl.port)
        with mochad.REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.ctrl.reconnect()
                self.send_cmd('off')
                # No read data on CM19A which is rf only
                if self._comm_type == 'pl':
                    self._controller.ctrl.read_data()
                self._state = False
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)

    def _get_device_status(self):
        """Get the status of the switch from mochad."""
        from pymochad import device

        if self._controller.ctrl and self._controller.connect_event.wait():
            switch = device.Device(self._controller.ctrl, self._address,
                                   comm_type=self._comm_type)
            with mochad.REQ_LOCK:
                status = switch.get_status().rstrip()
        else:
            status = 'off'
        return status == 'on'

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
