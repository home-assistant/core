"""Constants for the Airgradient integration."""

from dataclasses import dataclass
import logging

from airgradient import ApiVersion, Config, PmStandard

DOMAIN = "airgradient"

LOGGER = logging.getLogger(__package__)

PM_STANDARD = {
    PmStandard.UGM3: "ugm3",
    PmStandard.USAQI: "us_aqi",
}
PM_STANDARD_REVERSE = {v: k for k, v in PM_STANDARD.items()}

CONFIGURATION_CONTROL = "configuration_control"
CO2_ABC = "co2_automatic_baseline_calibration_days"
NOX_LEARNING_OFFSET = "nox_learning_offset"
TVOC_LEARNING_OFFSET = "tvoc_learning_offset"
POST_DATA = "post_data_to_airgradient"
PM_STANDARD_CONFIG = "pm_standard"
TEMPERATURE_UNIT = "temperature_unit"
LED_BAR_MODE = "led_bar_mode"
LED_BAR_BRIGHTNESS = "led_bar_brightness"
DISPLAY_BRIGHTNESS = "display_brightness"
GPS_MODE = "gps_mode"
FRONT_LED_BRIGHTNESS = "front_led_brightness"
BACK_LED_BRIGHTNESS = "back_led_brightness"
TOUCH_LED_INTENSITY = "touch_led_intensity"
BUZZER_ENABLED = "buzzer_enabled"
CLOUD_CONNECTION = "cloud_connection"

CO2_CALIBRATION = "co2_calibration"
LED_BAR_TEST = "led_bar_test"


@dataclass(frozen=True, kw_only=True)
class ModelCapabilities:
    """Configuration and action capabilities for a device model."""

    config: frozenset[str]
    actions: frozenset[str]


COMMON_LEGACY_CONFIG = frozenset(
    {
        CONFIGURATION_CONTROL,
        CO2_ABC,
        NOX_LEARNING_OFFSET,
        TVOC_LEARNING_OFFSET,
        POST_DATA,
    }
)

GO_CONFIG = frozenset(
    {
        CONFIGURATION_CONTROL,
        CO2_ABC,
        NOX_LEARNING_OFFSET,
        TVOC_LEARNING_OFFSET,
        PM_STANDARD_CONFIG,
        TEMPERATURE_UNIT,
        GPS_MODE,
        FRONT_LED_BRIGHTNESS,
        BACK_LED_BRIGHTNESS,
        TOUCH_LED_INTENSITY,
        BUZZER_ENABLED,
        CLOUD_CONNECTION,
    }
)

OUTDOOR_CAPABILITIES = ModelCapabilities(
    config=COMMON_LEGACY_CONFIG,
    actions=frozenset({CO2_CALIBRATION}),
)

MODEL_CAPABILITIES: tuple[tuple[str, ModelCapabilities], ...] = (
    (
        "I-9PSL",
        ModelCapabilities(
            config=COMMON_LEGACY_CONFIG
            | {
                PM_STANDARD_CONFIG,
                TEMPERATURE_UNIT,
                LED_BAR_MODE,
                LED_BAR_BRIGHTNESS,
                DISPLAY_BRIGHTNESS,
            },
            actions=frozenset({CO2_CALIBRATION, LED_BAR_TEST}),
        ),
    ),
    ("O-1", OUTDOOR_CAPABILITIES),
    ("0-1PS", OUTDOOR_CAPABILITIES),
    (
        "DIY",
        ModelCapabilities(
            config=COMMON_LEGACY_CONFIG
            | {
                PM_STANDARD_CONFIG,
                TEMPERATURE_UNIT,
                DISPLAY_BRIGHTNESS,
            },
            actions=frozenset({CO2_CALIBRATION}),
        ),
    ),
    (
        "P-1PSG",
        ModelCapabilities(
            config=GO_CONFIG,
            actions=frozenset({CO2_CALIBRATION, LED_BAR_TEST}),
        ),
    ),
)


def get_model_capabilities(model: str) -> ModelCapabilities | None:
    """Return capabilities for a recognized model."""
    for prefix, capabilities in MODEL_CAPABILITIES:
        if model.startswith(prefix):
            return capabilities
    return None


def supports_config(
    model: str, api_version: ApiVersion | None, config: Config, capability: str
) -> bool:
    """Return whether a device supports a configuration capability."""
    capabilities = get_model_capabilities(model)
    if api_version is ApiVersion.V1:
        return getattr(config, capability) is not None and (
            capabilities is None or capability in capabilities.config
        )
    return capabilities is not None and capability in capabilities.config


def supports_action(model: str, action: str) -> bool:
    """Return whether a device supports an action."""
    capabilities = get_model_capabilities(model)
    return capabilities is not None and action in capabilities.actions
