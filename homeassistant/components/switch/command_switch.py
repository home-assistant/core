# -*- coding: utf-8 -*-
"""
homeassistant.components.switch.command_switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Allows to configure custom shell commands to turn a switch on/off.
"""
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

    for dev_name, properties in switches.items():
        devices.append(
            CommandSwitch(
                dev_name,
                properties.get('oncmd', 'true'),
                properties.get('offcmd', 'true')))

    add_devices_callback(devices)


class CommandSwitch(ToggleEntity):
    """ Represents a switch that can be togggled using shell commands """
    def __init__(self, name, command_on, command_off):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = STATE_OFF
        self._command_on = command_on
        self._command_off = command_off

    @staticmethod
    def _switch(command):
        """ Execute the actual commands """
        _LOGGER.info('Running command: %s', command)

        success = (subprocess.call(command, shell=True) == 0)

        if not success:
            _LOGGER.error('Command failed: %s', command)

        return success

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ The name of the switch """
        return self._name

    @property
    def state(self):
        """ Returns the state of the switch. """
        return self._state

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        if CommandSwitch._switch(self._command_on):
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        if CommandSwitch._switch(self._command_off):
            self._state = STATE_OFF
