"""Allows to configure custom shell commands to turn a value for a sensor."""

import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.sensor import CONF_STATE_CLASS, DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
)

LOGGER = logging.getLogger(__package__)

CONF_COMMAND_TIMEOUT = "command_timeout"
CONF_JSON_ATTRIBUTES = "json_attributes"
CONF_JSON_ATTRIBUTES_PATH = "json_attributes_path"
DEFAULT_TIMEOUT = 15
DOMAIN = "command_line"

PLATFORM_MAPPING = {
    BINARY_SENSOR_DOMAIN: Platform.BINARY_SENSOR,
    COVER_DOMAIN: Platform.COVER,
    NOTIFY_DOMAIN: Platform.NOTIFY,
    SENSOR_DOMAIN: Platform.SENSOR,
    SWITCH_DOMAIN: Platform.SWITCH,
}
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]

TRIGGER_ENTITY_OPTIONS = {
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_STATE_CLASS,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
}
