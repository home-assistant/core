"""Constants for the Flux integration."""

DOMAIN = "flux"
CONF_START_TIME = "start_time"
CONF_STOP_TIME = "stop_time"
CONF_START_CT = "start_colortemp"
CONF_SUNSET_CT = "sunset_colortemp"
CONF_STOP_CT = "stop_colortemp"
CONF_ADJUST_BRIGHTNESS = "adjust_brightness"
CONF_INTERVAL = "interval"

MODE_XY = "xy"
MODE_MIRED = "mired"
MODE_RGB = "rgb"

DEFAULT_START_COLOR_TEMP_KELVIN = 4000
DEFAULT_SUNSET_COLOR_TEMP_KELVIN = 3000
DEFAULT_STOP_COLOR_TEMP_KELVIN = 1900
DEFAULT_MODE = MODE_XY
