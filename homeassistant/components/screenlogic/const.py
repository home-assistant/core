"""Constants for the ScreenLogic integration."""
from screenlogicpy.const import COLOR_MODE

from homeassistant.util import slugify

DOMAIN = "screenlogic"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10

SERVICE_SET_COLOR_MODE = "set_color_mode"
ATTR_COLOR_MODE = "color_mode"
SUPPORTED_COLOR_MODES = {
    slugify(name): num for num, name in COLOR_MODE.NAME_FOR_NUM.items()
}

DISCOVERED_GATEWAYS = "_discovered_gateways"
