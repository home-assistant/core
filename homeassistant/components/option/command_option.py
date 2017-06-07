"""
homeassistant.components.option.command_option
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure custom shell commands to select an option.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/option.command_option/
"""
import logging
import subprocess

from homeassistant.components.option import OptionDevice

_LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return options controlled by shell commands. """

    options = config.get('options', {})
    devices = []

    commands = []
    for dev_name, properties in options.items():
        name = properties.get('name', dev_name)
        for cmd in properties.get('options', []):
            commands.append((cmd.get('name', name), cmd.get('cmd', 'true')))
        devices.append(CommandOption(name, commands))

    add_devices_callback(devices)


class CommandOption(OptionDevice):
    """ Represents an option that can be triggered by shell commands. """

    def __init__(self, name, commands):
        self._name = name
        self._commands = commands
        self._option = None

    @property
    def name(self):
        """ The name of the option. """
        return self._name

    @property
    def option(self):
        """ Returns none, because every option can be triggered. """
        return self._option

    @property
    def options(self):
        """ Returns the list of available options for this entity. """
        return [c[0] for c in self._commands]

    def switch(self, option, **kwargs):
        """ Select the option 'option' for this entity. """
        cmd = [c[1] for c in self._commands if c[0] == option][0]

        _LOGGER.info('Running command: %s', cmd)

        success = (subprocess.call(cmd, shell=True) == 0)

        if success:
            self._option = option
        else:
            _LOGGER.error('Command failed: %s', cmd)

        return success

