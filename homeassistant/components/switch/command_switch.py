# -*- coding: utf-8 -*-
"""
homeassistant.components.switch.command_switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure custom shell commands to turn a switch on/off.

Configuration:

To use the command_line switch you will need to add something like the
following to your configuration.yaml file.

switch:
  platform: command_switch
  switches:
    name_of_the_switch:
      oncmd: switch_command on for name_of_the_switch
      offcmd: switch_command off for name_of_the_switch

Variables:

These are the variables for the switches array:

name_of_the_switch
*Required
Name of the command switch. Multiple entries are possible.

oncmd
*Required
The action to take for on.

offcmd
*Required
The action to take for off.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.command_switch.html
"""
import logging
import subprocess

from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return switches controlled by shell commands. """

    switches = config.get('switches', {})
    devices = []

    for dev_name, properties in switches.items():
        devices.append(
            CommandSwitch(
                properties.get('name', dev_name),
                properties.get('oncmd', 'true'),
                properties.get('offcmd', 'true')))

    add_devices_callback(devices)


class CommandSwitch(SwitchDevice):
    """ Represents a switch that can be togggled using shell commands. """
    def __init__(self, name, command_on, command_off):
        self._name = name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off

    @staticmethod
    def _switch(command):
        """ Execute the actual commands. """
        _LOGGER.info('Running command: %s', command)

        success = (subprocess.call(command, shell=True) == 0)

        if not success:
            _LOGGER.error('Command failed: %s', command)

        return success

    @property
    def should_poll(self):
        """ No polling needed. """
        return False

    @property
    def name(self):
        """ The name of the switch. """
        return self._name

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        if CommandSwitch._switch(self._command_on):
            self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        if CommandSwitch._switch(self._command_off):
            self._state = False
        self.update_ha_state()
