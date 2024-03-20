"""Constants for the Flux integration."""

from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.const import CONF_MODE
from homeassistant.util.read_only_dict import ReadOnlyDict

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

DEFAULT_NAME = "Flux"
DEFAULT_START_COLOR_TEMP_KELVIN = 4000
DEFAULT_SUNSET_COLOR_TEMP_KELVIN = 3000
DEFAULT_STOP_COLOR_TEMP_KELVIN = 1900
DEFAULT_MODE = MODE_XY
DEFAULT_INTERVAL_DURATION = {"seconds": 30}
DEFAULT_TRANSITION_DURATION = {"seconds": 30}

DEFAULT_SETTINGS = ReadOnlyDict(
    {
        CONF_START_CT: DEFAULT_START_COLOR_TEMP_KELVIN,
        CONF_SUNSET_CT: DEFAULT_SUNSET_COLOR_TEMP_KELVIN,
        CONF_STOP_CT: DEFAULT_STOP_COLOR_TEMP_KELVIN,
        CONF_ADJUST_BRIGHTNESS: True,
        CONF_MODE: DEFAULT_MODE,
        CONF_INTERVAL: DEFAULT_INTERVAL_DURATION,
        ATTR_TRANSITION: DEFAULT_TRANSITION_DURATION,
    }
)
