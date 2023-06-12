"""Allows to configure custom shell commands to turn a value for a sensor."""

import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

CONF_COMMAND_TIMEOUT = "command_timeout"
DEFAULT_TIMEOUT = 15
DOMAIN = "command_line"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]
