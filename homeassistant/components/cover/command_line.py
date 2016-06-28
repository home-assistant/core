"""

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.command_line/
"""
import logging
import subprocess

from homeassistant.components.cover import CoverDevice
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup cover controlled by shell commands."""
    covers = config.get('covers', {})
    devices = []

    for dev_name, properties in covers.items():
        devices.append(
            CommandCover(
                hass,
                properties.get('name', dev_name),
                properties.get('upcmd', 'true'),
                properties.get('downcmd', 'true'),
                properties.get('stopcmd', 'true'),
                properties.get('statecmd', False),
                properties.get(CONF_VALUE_TEMPLATE, '{{ value }}')))
    add_devices_callback(devices)


# pylint: disable=too-many-arguments, too-many-instance-attributes
class CommandCover(CoverDevice):
    """Representation a command line cover."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name, command_open, command_close, command_stop,
                 command_state, value_template):
        """Initialize the cover."""
        self._hass = hass
        self._name = name
        self._state = None
        self._command_open = command_open
        self._command_close = command_close
        self._command_stop = command_stop
        self._command_state = command_state
        self._value_template = value_template

    @staticmethod
    def _send_cover_cmd(command):
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
        """Return the name of the cover."""
        return self._name

    @property
    def current_position(self):
        """Return current position of cover.

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
                payload = template.render_with_possible_json_value(
                    self._hass, self._value_template, payload)
            self._state = int(payload)

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._send_cover_cmd(self._command_open)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._send_cover_cmd(self._command_close)

    def stop_cover(self, **kwargs):
        """Stop the device."""
        self._send_cover_cmd(self._command_stop)
