"""Constants for the Template Platform Components."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

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

# Attribute with a dedicated option to that option, deprecated in 2026.12
BINARY_SENSOR_DEPRECATED_ATTRIBUTES_OPTIONS = {"device_class": "device_class"}
EVENT_DEPRECATED_ATTRIBUTES_OPTIONS = {
    "event_type": "event_type",
    "event_types": "event_types",
}
SENSOR_DEPRECATED_ATTRIBUTES_OPTIONS = {
    "device_class": "device_class",
    "state_class": "state_class",
    "last_reset": "last_reset",
}
VACUUM_DEPRECATED_ATTRIBUTES_OPTIONS = {
    "fan_speed": "fan_speed",
    "fan_speed_list": "fan_speeds",
}


@dataclass(frozen=True, kw_only=True)
class DeprecatedTemplateOptions:
    """Deprecated YAML options of a template platform that create repairs."""

    platform: Platform
    # Deprecated option to the option that replaces it
    options: Mapping[str, str]
    # Also the prefix of the issue ids
    translation_key: str
    blueprint_translation_key: str
    breaks_in_ha_version: str
    # The entity option holding the deprecated options, the entity config when None
    parent_option: str | None = None

    def options_config(self, entity_config: ConfigType) -> Mapping[Any, Any]:
        """Return the config holding the deprecated options of an entity."""
        if self.parent_option is None:
            return entity_config
        # A parent option rendered from a single template can't hold options
        if isinstance(options := entity_config.get(self.parent_option), dict):
            return options
        return {}


WEATHER_DEPRECATED_OPTIONS = DeprecatedTemplateOptions(
    platform=Platform.WEATHER,
    options=WEATHER_DEPRECATED_TEMPLATE_OPTIONS,
    translation_key="deprecated_weather_template_options",
    blueprint_translation_key="deprecated_weather_template_options_blueprint",
    breaks_in_ha_version="2027.6.0",
)

BINARY_SENSOR_DEPRECATED_ATTRIBUTES = DeprecatedTemplateOptions(
    platform=Platform.BINARY_SENSOR,
    options=BINARY_SENSOR_DEPRECATED_ATTRIBUTES_OPTIONS,
    translation_key="deprecated_binary_sensor_attributes",
    blueprint_translation_key="deprecated_binary_sensor_attributes_blueprint",
    breaks_in_ha_version="2027.6.0",
    parent_option=CONF_ATTRIBUTES,
)

EVENT_DEPRECATED_ATTRIBUTES = DeprecatedTemplateOptions(
    platform=Platform.EVENT,
    options=EVENT_DEPRECATED_ATTRIBUTES_OPTIONS,
    translation_key="deprecated_event_attributes",
    blueprint_translation_key="deprecated_event_attributes_blueprint",
    breaks_in_ha_version="2027.6.0",
    parent_option=CONF_ATTRIBUTES,
)

SENSOR_DEPRECATED_ATTRIBUTES = DeprecatedTemplateOptions(
    platform=Platform.SENSOR,
    options=SENSOR_DEPRECATED_ATTRIBUTES_OPTIONS,
    translation_key="deprecated_sensor_attributes",
    blueprint_translation_key="deprecated_sensor_attributes_blueprint",
    breaks_in_ha_version="2027.6.0",
    parent_option=CONF_ATTRIBUTES,
)

VACUUM_DEPRECATED_ATTRIBUTES = DeprecatedTemplateOptions(
    platform=Platform.VACUUM,
    options=VACUUM_DEPRECATED_ATTRIBUTES_OPTIONS,
    translation_key="deprecated_vacuum_attributes",
    blueprint_translation_key="deprecated_vacuum_attributes_blueprint",
    breaks_in_ha_version="2027.6.0",
    parent_option=CONF_ATTRIBUTES,
)

DEPRECATED_TEMPLATE_OPTIONS = (
    WEATHER_DEPRECATED_OPTIONS,
    BINARY_SENSOR_DEPRECATED_ATTRIBUTES,
    EVENT_DEPRECATED_ATTRIBUTES,
    SENSOR_DEPRECATED_ATTRIBUTES,
    VACUUM_DEPRECATED_ATTRIBUTES,
)


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
