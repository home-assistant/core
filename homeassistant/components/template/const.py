"""Constants for the Template Platform Components."""

import logging

from homeassistant.const import Platform

CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"
CONF_TRIGGER = "trigger"

DOMAIN = "template"

PLATFORM_STORAGE_KEY = "template_platforms"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
    Platform.WEATHER,
]

CONF_AVAILABILITY = "availability"
CONF_ATTRIBUTES = "attributes"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"
CONF_BLUEPRINT_INPUTS = "BLUEPRINT_INPUTS"
CONF_PICTURE = "picture"
CONF_OBJECT_ID = "object_id"

LOGGER = logging.getLogger(__package__)
