"""Constants of the FluxLed/MagicHome Integration."""

import asyncio
import socket
from typing import Final

from flux_led.const import (
    COLOR_MODE_CCT as FLUX_COLOR_MODE_CCT,
    COLOR_MODE_RGB as FLUX_COLOR_MODE_RGB,
    COLOR_MODE_RGBW as FLUX_COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW as FLUX_COLOR_MODE_RGBWW,
)

from homeassistant.components.light import (
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
)

DOMAIN: Final = "flux_led"

MIN_RGB_BRIGHTNESS: Final = 1
MIN_CCT_BRIGHTNESS: Final = 2

FLUX_COLOR_MODE_TO_HASS: Final = {
    FLUX_COLOR_MODE_RGB: COLOR_MODE_RGB,
    FLUX_COLOR_MODE_RGBW: COLOR_MODE_RGBW,
    FLUX_COLOR_MODE_RGBWW: COLOR_MODE_RGBWW,
    FLUX_COLOR_MODE_CCT: COLOR_MODE_COLOR_TEMP,
}

MULTI_BRIGHTNESS_COLOR_MODES: Final = {COLOR_MODE_RGBWW, COLOR_MODE_RGBW}

API: Final = "flux_api"

SIGNAL_STATE_UPDATED = "flux_led_{}_state_updated"

DEFAULT_NETWORK_SCAN_INTERVAL: Final = 120
DEFAULT_SCAN_INTERVAL: Final = 5
DEFAULT_EFFECT_SPEED: Final = 50

FLUX_LED_DISCOVERY: Final = "flux_led_discovery"

FLUX_LED_EXCEPTIONS: Final = (
    asyncio.TimeoutError,
    socket.error,
    RuntimeError,
    BrokenPipeError,
)

STARTUP_SCAN_TIMEOUT: Final = 5
DISCOVER_SCAN_TIMEOUT: Final = 10
DIRECTED_DISCOVERY_TIMEOUT: Final = 15

CONF_MODEL: Final = "model"
CONF_MODEL_NUM: Final = "model_num"
CONF_MODEL_INFO: Final = "model_info"
CONF_MODEL_DESCRIPTION: Final = "model_description"
CONF_MINOR_VERSION: Final = "minor_version"
CONF_REMOTE_ACCESS_ENABLED: Final = "remote_access_enabled"
CONF_REMOTE_ACCESS_HOST: Final = "remote_access_host"
CONF_REMOTE_ACCESS_PORT: Final = "remote_access_port"
CONF_WHITE_CHANNEL_TYPE: Final = "white_channel_type"


TRANSITION_GRADUAL: Final = "gradual"
TRANSITION_JUMP: Final = "jump"
TRANSITION_STROBE: Final = "strobe"

CONF_COLORS: Final = "colors"
CONF_SPEED_PCT: Final = "speed_pct"
CONF_TRANSITION: Final = "transition"
CONF_EFFECT: Final = "effect"


EFFECT_SPEED_SUPPORT_MODES: Final = {COLOR_MODE_RGB, COLOR_MODE_RGBW, COLOR_MODE_RGBWW}


CONF_CUSTOM_EFFECT_COLORS: Final = "custom_effect_colors"
CONF_CUSTOM_EFFECT_SPEED_PCT: Final = "custom_effect_speed_pct"
CONF_CUSTOM_EFFECT_TRANSITION: Final = "custom_effect_transition"
