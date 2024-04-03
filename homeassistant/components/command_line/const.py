"""Allows to configure custom shell commands to turn a value for a sensor."""

import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

CONF_COMMAND_TIMEOUT = "command_timeout"
CONF_JSON_ATTRIBUTES = "json_attributes"
CONF_JSON_ATTRIBUTES_PATH = "json_attributes_path"
DEFAULT_TIMEOUT = 15
DOMAIN = "command_line"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]
