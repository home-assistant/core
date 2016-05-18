"""
Support for custom shell commands to turn a switch on/off.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.command_line/
"""
import logging
import subprocess

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return switches controlled by shell commands."""
    switches = config.get('switches', {})
    devices = []

    for dev_name, properties in switches.items():
        devices.append(
            CommandSwitch(
                hass,
                properties.get('name', dev_name),
                properties.get('oncmd', 'true'),
                properties.get('offcmd', 'true'),
                properties.get('statecmd', False),
                properties.get(CONF_VALUE_TEMPLATE, False)))

    add_devices_callback(devices)


# pylint: disable=too-many-instance-attributes
class CommandSwitch(SwitchDevice):
    """Representation a switch that can be toggled using shell commands."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name, command_on, command_off,
                 command_state, value_template):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off
        self._command_state = command_state
        self._value_template = value_template

    @staticmethod
    def _switch(command):
        """Execute the actual commands."""
        _LOGGER.info('Running command: %s', command)

        success = (subprocess.call(command, shell=True) == 0)

        if not success:
            _LOGGER.error('Command failed: %s', command)

        return success

    @staticmethod
    def _query_state_value(command):
        """Execute state command for return value."""
        _LOGGER.info('Running state command: %s', command)

        try:
            return_value = subprocess.check_output(command, shell=True)
            return return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error('Command failed: %s', command)

    @staticmethod
    def _query_state_code(command):
        """Execute state command for return code."""
        _LOGGER.info('Running state command: %s', command)
        return subprocess.call(command, shell=True) == 0

    @property
    def should_poll(self):
        """Only poll if we have state command."""
        return self._command_state is not None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._command_state is False

    def _query_state(self):
        """Query for state."""
        if not self._command_state:
            _LOGGER.error('No state command specified')
            return
        if self._value_template:
            return CommandSwitch._query_state_value(self._command_state)
        return CommandSwitch._query_state_code(self._command_state)

    def update(self):
        """Update device state."""
        if self._command_state:
            payload = str(self._query_state())
            if self._value_template:
                payload = template.render_with_possible_json_value(
                    self._hass, self._value_template, payload)
            self._state = (payload.lower() == "true")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if (CommandSwitch._switch(self._command_on) and
                not self._command_state):
            self._state = True
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if (CommandSwitch._switch(self._command_off) and
                not self._command_state):
            self._state = False
            self.update_ha_state()
