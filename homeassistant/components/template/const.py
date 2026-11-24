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


# Legacy weather option to its replacement, deprecated in 2026.12
WEATHER_DEPRECATED_TEMPLATE_OPTIONS = {
    "apparent_temperature_template": "apparent_temperature",
    "attribution_template": "attribution",
    "cloud_coverage_template": "cloud_coverage",
    "condition_template": "condition",
    "dew_point_template": "dew_point",
    "forecast_daily_template": "forecast_daily",
    "forecast_hourly_template": "forecast_hourly",
    "forecast_twice_daily_template": "forecast_twice_daily",
    "humidity_template": "humidity",
    "ozone_template": "ozone",
    "pressure_template": "pressure",
    "temperature_template": "temperature",
    "uv_index_template": "uv_index",
    "visibility_template": "visibility",
    "wind_bearing_template": "wind_bearing",
    "wind_gust_speed_template": "wind_gust_speed",
    "wind_speed_template": "wind_speed",
}


class TemplateConfig(dict):
    """Dummy class to allow adding attributes."""

    raw_config: ConfigType | None = None
    raw_blueprint_inputs: ConfigType | None = None
    # The file and line annotations are dropped from the config after validation,
    # keep them for the deprecated options per platform and entity for repairs
    option_locations: dict[str, list[dict[str, tuple[str, int]]]] | None = None


class TemplateConfigSections(list[TemplateConfig]):
    """Validated template config sections."""

    # Sections which failed validation are left out of the list
    has_invalid_sections: bool = False


class TemplateService(StrEnum):
    """Store keys for template services."""

    RELOAD = "reload"
