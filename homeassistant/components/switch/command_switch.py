# -*- coding: utf-8 -*-
import logging
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME
import subprocess

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return switches controlled by shell commands. """

    switches = config.get('switches', {})
    devices = []

    for k, v in switches.items():
        devices.append(
            CommandSwitch(
                k,
                v.get('oncmd', 'true'),
                v.get('offcmd', 'true')))

    add_devices_callback(devices)


class CommandSwitch(ToggleEntity):
    def __init__(self, name, command_on, command_off):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = STATE_OFF
        self._command_on = command_on
        self._command_off = command_off

    @staticmethod
    def _switch(command):
        _LOGGER.info('Running command: {}'.format(command))

        success = (subprocess.call(command, shell=True) == 0)

        if not success:
            _LOGGER.error('Command failed: {}'.format(command))

        return success

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def is_on(self):
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        if CommandSwitch._switch(self._command_on):
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        if CommandSwitch._switch(self._command_off):
            self._state = STATE_OFF

