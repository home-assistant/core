"""Data Schema for command line."""
from __future__ import annotations

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_DEVICE_CLASSES,
)
from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_FRIENDLY_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_ICON_TEMPLATE,
)

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT

DEFAULT_NAME = "Command Line"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
CONF_JSON_ATTRIBUTES = "json_attributes"

DATA_COMMON = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
}
DATA_UNIQUE_ID = {
    vol.Optional(CONF_UNIQUE_ID): cv.string,
}

DATA_BINARY_SENSOR = {
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): BINARY_DEVICE_CLASSES,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
}


DATA_SENSOR = {
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_JSON_ATTRIBUTES): cv.ensure_list_csv,
    vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
}


DATA_COVER = {
    vol.Optional(CONF_COMMAND_CLOSE, default="true"): cv.string,
    vol.Optional(CONF_COMMAND_OPEN, default="true"): cv.string,
    vol.Optional(CONF_COMMAND_STATE): cv.string,
    vol.Optional(CONF_COMMAND_STOP, default="true"): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
}

DATA_NOTIFY = {
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
}

DATA_SWITCH = {
    vol.Optional(CONF_COMMAND_OFF, default="true"): cv.string,
    vol.Optional(CONF_COMMAND_ON, default="true"): cv.string,
    vol.Optional(CONF_COMMAND_STATE): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
}
