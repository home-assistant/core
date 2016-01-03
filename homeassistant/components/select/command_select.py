"""
homeassistant.components.select.command_select
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure custom shell commands to select an option.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/select.command_select/
"""
import logging
import subprocess

from homeassistant.components.select import SelectableDevice

_LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return selects controlled by shell commands. """

    selects = config.get('select', {})
    devices = []

    commands = []
    for dev_name, properties in selects.items():
        name = properties.get('name', dev_name)
        for cmd in properties.get('options', []):
            commands.append((cmd.get('name', name), cmd.get('cmd', 'true')))
        devices.append(CommandSelect(name, commands))

    add_devices_callback(devices)


class CommandSelect(SelectableDevice):
    """ Represents a selectbox group that can be triggered by shell commands. """

    def __init__(self, name, commands):
        self._name = name
        self._commands = commands
        self._option = None

    @property
    def name(self):
        """ The name of the select box. """
        return self._name

    @property
    def state(self):
        """ Returns the last selected option. """
        return self._option

    @property
    def options(self):
        """ Returns the list of available options for this entity. """
        return [c[0] for c in self._commands]

    def select(self, option, **kwargs):
        """ Select the option 'option' for this entity. """
        cmd = [c[1] for c in self._commands if c[0] == option][0]

        _LOGGER.info('Running command: %s', cmd)

        success = (subprocess.call(cmd, shell=True) == 0)

        if success:
            self._option = option
        else:
            _LOGGER.error('Command failed: %s', cmd)

        return success

