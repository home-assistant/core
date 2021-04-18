"""Constants for the ScreenLogic integration."""
from screenlogicpy.const import COLOR_MODE

from homeassistant.util import slugify

DOMAIN = "screenlogic"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10

ATTR_COLOR_MODE = "color_mode"
SUPPORTED_COLOR_MODES = {
    slugify(name): num for num, name in COLOR_MODE.NAME_FOR_NUM.items()
}
SET_COLOR_MODE_SERVICE_DESCRIPTION = {
    "name": "Set Color Mode",
    "description": "Sets the color mode for all color-capable lights attached to this ScreenLogic gateway.",
    "fields": {
        "color_mode": {
            "name": "Color Mode",
            "description": "The ScreenLogic color mode to set.",
            "required": True,
            "example": "romance",
            "default": "all_off",
            "selector": {
                "select": {"options": [*SUPPORTED_COLOR_MODES]},
            },
        },
    },
}

DISCOVERED_GATEWAYS = "_discovered_gateways"
