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


FLUX_COLOR_MODE_TO_HASS: Final = {
    FLUX_COLOR_MODE_RGB: COLOR_MODE_RGB,
    FLUX_COLOR_MODE_RGBW: COLOR_MODE_RGBW,
    FLUX_COLOR_MODE_RGBWW: COLOR_MODE_RGBWW,
    FLUX_COLOR_MODE_CCT: COLOR_MODE_COLOR_TEMP,
}


API: Final = "flux_api"

SIGNAL_STATE_UPDATED = "flux_led_{}_state_updated"

CONF_AUTOMATIC_ADD: Final = "automatic_add"
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

CONF_DEVICES: Final = "devices"
CONF_CUSTOM_EFFECT: Final = "custom_effect"
CONF_MODEL: Final = "model"

MODE_AUTO: Final = "auto"
MODE_RGB: Final = "rgb"
MODE_RGBW: Final = "rgbw"

# This mode enables white value to be controlled by brightness.
# RGB value is ignored when this mode is specified.
MODE_WHITE: Final = "w"

TRANSITION_GRADUAL: Final = "gradual"
TRANSITION_JUMP: Final = "jump"
TRANSITION_STROBE: Final = "strobe"

CONF_COLORS: Final = "colors"
CONF_SPEED_PCT: Final = "speed_pct"
CONF_TRANSITION: Final = "transition"


EFFECT_SUPPORT_MODES = {COLOR_MODE_RGB, COLOR_MODE_RGBW, COLOR_MODE_RGBWW}


CONF_CUSTOM_EFFECT_COLORS: Final = "custom_effect_colors"
CONF_CUSTOM_EFFECT_SPEED_PCT: Final = "custom_effect_speed_pct"
CONF_CUSTOM_EFFECT_TRANSITION: Final = "custom_effect_transition"
