"""Constants for the Template Platform Components."""

import voluptuous as vol

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_UNIQUE_ID, Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

CONF_ADVANCED_OPTIONS = "advanced_options"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"
CONF_ATTRIBUTES = "attributes"
CONF_AVAILABILITY = "availability"
CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_MAX = "max"
CONF_MIN = "min"
CONF_OBJECT_ID = "object_id"
CONF_PICTURE = "picture"
CONF_PRESS = "press"
CONF_STEP = "step"
CONF_TURN_OFF = "turn_off"
CONF_TURN_ON = "turn_on"

TEMPLATE_ENTITY_BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ICON): cv.template,
        vol.Optional(CONF_NAME): cv.template,
        vol.Optional(CONF_PICTURE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

DOMAIN = "template"

PLATFORM_STORAGE_KEY = "template_platforms"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.FAN,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
    Platform.WEATHER,
]


class TemplateConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: ConfigType | None = None
    raw_blueprint_inputs: ConfigType | None = None
