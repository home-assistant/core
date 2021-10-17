"""Constants of the FluxLed/MagicHome Integration."""

import asyncio
import socket
from typing import Final

DOMAIN: Final = "flux_led"

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


CONF_CUSTOM_EFFECT_COLORS: Final = "custom_effect_colors"
CONF_CUSTOM_EFFECT_SPEED_PCT: Final = "custom_effect_speed_pct"
CONF_CUSTOM_EFFECT_TRANSITION: Final = "custom_effect_transition"

FLUX_HOST: Final = "ipaddr"
FLUX_MAC: Final = "id"
FLUX_MODEL: Final = "model"
