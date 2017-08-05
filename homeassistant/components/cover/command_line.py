"""
Support for command line covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.command_line/
"""
import logging
import subprocess

import voluptuous as vol

from homeassistant.components.cover import (CoverDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_COMMAND_CLOSE, CONF_COMMAND_OPEN, CONF_COMMAND_STATE,
    CONF_COMMAND_STOP, CONF_COVERS, CONF_VALUE_TEMPLATE, CONF_FRIENDLY_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

COVER_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMAND_CLOSE, default='true'): cv.string,
    vol.Optional(CONF_COMMAND_OPEN, default='true'): cv.string,
    vol.Optional(CONF_COMMAND_STATE): cv.string,
    vol.Optional(CONF_COMMAND_STOP, default='true'): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up cover controlled by shell commands."""
    devices = config.get(CONF_COVERS, {})
    covers = []

    for device_name, device_config in devices.items():
        value_template = device_config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = hass

        covers.append(
            CommandCover(
                hass,
                device_config.get(CONF_FRIENDLY_NAME, device_name),
                device_config.get(CONF_COMMAND_OPEN),
                device_config.get(CONF_COMMAND_CLOSE),
                device_config.get(CONF_COMMAND_STOP),
                device_config.get(CONF_COMMAND_STATE),
                value_template,
            )
        )

    if not covers:
        _LOGGER.error("No covers added")
        return False

    add_devices(covers)


class CommandCover(CoverDevice):
    """Representation a command line cover."""

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
    def _move_cover(command):
        """Execute the actual commands."""
        _LOGGER.info("Running command: %s", command)

        success = (subprocess.call(command, shell=True) == 0)

        if not success:
            _LOGGER.error("Command failed: %s", command)

        return success

    @staticmethod
    def _query_state_value(command):
        """Execute state command for return value."""
        _LOGGER.info("Running state command: %s", command)

        try:
            return_value = subprocess.check_output(command, shell=True)
            return return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error("Command failed: %s", command)

    @property
    def should_poll(self):
        """Only poll if we have state command."""
        return self._command_state is not None

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            return self.current_cover_position == 0

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._state

    def _query_state(self):
        """Query for the state."""
        if not self._command_state:
            _LOGGER.error("No state command specified")
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

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._move_cover(self._command_open)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._move_cover(self._command_close)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._move_cover(self._command_stop)
