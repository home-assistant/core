"""Constants for the ScreenLogic integration."""
from screenlogicpy.const import CIRCUIT_FUNCTION, COLOR_MODE

from homeassistant.util import slugify

DOMAIN = "screenlogic"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10

SERVICE_SET_COLOR_MODE = "set_color_mode"
ATTR_COLOR_MODE = "color_mode"
SUPPORTED_COLOR_MODES = {
    slugify(name): num for num, name in COLOR_MODE.NAME_FOR_NUM.items()
}

SERVICE_SET_SCG = "set_scg"
ATTR_POOL_PERCENT = "pool_percent"
ATTR_SPA_PERCENT = "spa_percent"

LIGHT_CIRCUIT_FUNCTIONS = {CIRCUIT_FUNCTION.INTELLIBRITE, CIRCUIT_FUNCTION.LIGHT}
