"""Constants of the FluxLed/MagicHome Integration."""

DOMAIN = "flux_led"

API = "flux_api"

CONF_AUTOMATIC_ADD = "automatic_add"
DEFAULT_NETWORK_SCAN_INTERVAL = 120
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_EFFECT_SPEED = 50


DEFAULT_SPEED = 70

CONF_EFFECT_SPEED = "effect_speed"
CONF_DEVICES = "devices"
CONF_CUSTOM_EFFECT = "custom_effect"
CONF_MODEL = "model"

MODE_AUTO = "auto"
MODE_RGB = "rgb"
MODE_RGBW = "rgbw"
MODE_RGBCW = "rgbcw"
MODE_RGBWW = "rgbww"

# This mode enables white value to be controlled by brightness.
# RGB value is ignored when this mode is specified.
MODE_WHITE = "w"

TRANSITION_GRADUAL = "gradual"
TRANSITION_JUMP = "jump"
TRANSITION_STROBE = "strobe"

CONF_COLORS = "colors"
CONF_SPEED_PCT = "speed_pct"
CONF_TRANSITION = "transition"


CONF_CUSTOM_EFFECT_COLORS = "custom_effect_colors"
CONF_CUSTOM_EFFECT_SPEED_PCT = "custom_effect_speed_pct"
CONF_CUSTOM_EFFECT_TRANSITION = "custom_effect_transition"

FLUX_HOST = "ipaddr"
FLUX_MAC = "id"
FLUX_MODEL = "model"
