"""Constants for the Template Platform Components."""

from homeassistant.components.blueprint import BLUEPRINT_SCHEMA
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

CONF_ACTION = "action"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"
CONF_ATTRIBUTES = "attributes"
CONF_AVAILABILITY = "availability"
CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_CONDITION = "condition"
CONF_MAX = "max"
CONF_MIN = "min"
CONF_OBJECT_ID = "object_id"
CONF_PICTURE = "picture"
CONF_PRESS = "press"
CONF_STEP = "step"
CONF_TRIGGER = "trigger"
CONF_TURN_OFF = "turn_off"
CONF_TURN_ON = "turn_on"

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

TEMPLATE_BLUEPRINT_SCHEMA = BLUEPRINT_SCHEMA


class TemplateConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: ConfigType | None = None
    raw_blueprint_inputs: ConfigType | None = None
