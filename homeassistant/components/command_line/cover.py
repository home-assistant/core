"""Support for command line covers."""
import logging

import voluptuous as vol

from homeassistant.components.cover import PLATFORM_SCHEMA, CoverEntity
from homeassistant.const import (
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_COVERS,
    CONF_FRIENDLY_NAME,
    CONF_VALUE_TEMPLATE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import setup_reload_service

from . import call_shell_with_timeout, check_output_or_log
from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

COVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_CLOSE, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_OPEN, default="true"): cv.string,
        vol.Optional(CONF_COMMAND_STATE): cv.string,
        vol.Optional(CONF_COMMAND_STOP, default="true"): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA)}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up cover controlled by shell commands."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)

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
                device_config[CONF_COMMAND_OPEN],
                device_config[CONF_COMMAND_CLOSE],
                device_config[CONF_COMMAND_STOP],
                device_config.get(CONF_COMMAND_STATE),
                value_template,
                device_config[CONF_COMMAND_TIMEOUT],
            )
        )

    if not covers:
        _LOGGER.error("No covers added")
        return False

    add_entities(covers)


class CommandCover(CoverEntity):
    """Representation a command line cover."""

    def __init__(
        self,
        hass,
        name,
        command_open,
        command_close,
        command_stop,
        command_state,
        value_template,
        timeout,
    ):
        """Initialize the cover."""
        self._hass = hass
        self._name = name
        self._state = None
        self._command_open = command_open
        self._command_close = command_close
        self._command_stop = command_stop
        self._command_state = command_state
        self._value_template = value_template
        self._timeout = timeout

    def _move_cover(self, command):
        """Execute the actual commands."""
        _LOGGER.info("Running command: %s", command)

        success = call_shell_with_timeout(command, self._timeout) == 0

        if not success:
            _LOGGER.error("Command failed: %s", command)

        return success

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
        _LOGGER.info("Running state value command: %s", self._command_state)
        return check_output_or_log(self._command_state, self._timeout)

    def update(self):
        """Update device state."""
        if self._command_state:
            payload = str(self._query_state())
            if self._value_template:
                payload = self._value_template.render_with_possible_json_value(payload)
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
