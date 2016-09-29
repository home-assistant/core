"""
Support for command roller shutters.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter.command_line/
"""
import logging
import subprocess

from homeassistant.components.rollershutter import RollershutterDevice
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers.template import Template

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup roller shutter controlled by shell commands."""
    rollershutters = config.get('rollershutters', {})
    devices = []

    for dev_name, properties in rollershutters.items():
        value_template = properties.get(CONF_VALUE_TEMPLATE)

        if value_template is not None:
            value_template = Template(value_template, hass)

        devices.append(
            CommandRollershutter(
                hass,
                properties.get('name', dev_name),
                properties.get('upcmd', 'true'),
                properties.get('downcmd', 'true'),
                properties.get('stopcmd', 'true'),
                properties.get('statecmd', False),
                value_template))
    add_devices_callback(devices)


# pylint: disable=abstract-method
# pylint: disable=too-many-arguments, too-many-instance-attributes
class CommandRollershutter(RollershutterDevice):
    """Representation a command line roller shutter."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name, command_up, command_down, command_stop,
                 command_state, value_template):
        """Initialize the roller shutter."""
        self._hass = hass
        self._name = name
        self._state = None
        self._command_up = command_up
        self._command_down = command_down
        self._command_stop = command_stop
        self._command_state = command_state
        self._value_template = value_template

    @staticmethod
    def _move_rollershutter(command):
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

    @property
    def should_poll(self):
        """Only poll if we have state command."""
        return self._command_state is not None

    @property
    def name(self):
        """Return the name of the roller shutter."""
        return self._name

    @property
    def current_position(self):
        """Return current position of roller shutter.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._state

    def _query_state(self):
        """Query for the state."""
        if not self._command_state:
            _LOGGER.error('No state command specified')
            return
        return self._query_state_value(self._command_state)

    def update(self):
        """Update device state."""
        if self._command_state:
            payload = str(self._query_state())
            if self._value_template:
                payload = self._value_template.render_with_possible_json_value(
                    payload)
            self._state = int(payload)

    def move_up(self, **kwargs):
        """Move the roller shutter up."""
        self._move_rollershutter(self._command_up)

    def move_down(self, **kwargs):
        """Move the roller shutter down."""
        self._move_rollershutter(self._command_down)

    def stop(self, **kwargs):
        """Stop the device."""
        self._move_rollershutter(self._command_stop)
