"""Constants for the Template Platform Components."""

from enum import StrEnum

from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

CONF_ADDITIONAL_OPTIONS = "additional_options"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"
CONF_ATTRIBUTES = "attributes"
CONF_AVAILABILITY = "availability"
CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_DEFAULT_ENTITY_ID = "default_entity_id"
CONF_MAX = "max"
CONF_MIN = "min"
CONF_PICTURE = "picture"
CONF_PRESS = "press"
CONF_STEP = "step"
CONF_TRIGGER_VARIABLES = "trigger_variables"
CONF_TURN_OFF = "turn_off"
CONF_TURN_ON = "turn_on"

DOMAIN = "template"

PLATFORM_STORAGE_KEY = "template_platforms"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.FAN,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.VACUUM,
    Platform.WATER_HEATER,
    Platform.WEATHER,
]

DEFAULT_NAMES: dict[Platform, str] = {
    Platform.ALARM_CONTROL_PANEL: "Template Alarm Control Panel",
    Platform.BINARY_SENSOR: "Template Binary Sensor",
    Platform.BUTTON: "Template Button",
    Platform.CLIMATE: "Template Climate",
    Platform.COVER: "Template Cover",
    Platform.DEVICE_TRACKER: "Template Device Tracker",
    Platform.EVENT: "Template Event",
    Platform.FAN: "Template Fan",
    Platform.IMAGE: "Template Image",
    Platform.LIGHT: "Template Light",
    Platform.LOCK: "Template Lock",
    Platform.MEDIA_PLAYER: "Template Media Player",
    Platform.NUMBER: "Template Number",
    Platform.SELECT: "Template Select",
    Platform.SENSOR: "Template Sensor",
    Platform.SWITCH: "Template Switch",
    Platform.UPDATE: "Template Update",
    Platform.VACUUM: "Template Vacuum",
    Platform.WATER_HEATER: "Template Water Heater",
    Platform.WEATHER: "Template Weather",
}


class TemplateConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: ConfigType | None = None
    raw_blueprint_inputs: ConfigType | None = None


class TemplateService(StrEnum):
    """Store keys for template services."""

    RELOAD = "reload"
