"""Constants for OSO Energy."""
from typing import Any

from homeassistant.components.water_heater import STATE_PERFORMANCE
from homeassistant.const import STATE_OFF, STATE_ON, Platform

ATTR_UNTIL_TEMP_LIMIT = "until_temp_limit"
ATTR_V40MIN = "v40_min"
CONFIG_ENTRY_VERSION = 1
DOMAIN = "osoenergy"

EXTRA_HEATER_ATTR: dict[str, dict[str, Any]] = {
    "heater_state": {
        "ha_name": "heater_state",
        "value_mapping": {
            "on": STATE_ON,
            "off": STATE_OFF,
        },
    },
    "heater_mode": {
        "ha_name": "heater_mode",
        "value_mapping": {
            "auto": "auto",
            "manual": "manual",
            "off": STATE_OFF,
            "legionella": "legionella",
            "powersave": "power_save",
            "extraenergy": "extra_energy",
            "voltage": "voltage",
            "ffr": "ffr",
        },
    },
    "optimization_mode": {
        "ha_name": "optimization_mode",
        "value_mapping": {
            "off": STATE_OFF,
            "oso": "oso",
            "gridcompany": "grid_company",
            "smartcompany": "smart_company",
            "advanced": "advanced",
        },
    },
    "profile": {"ha_name": "profile", "is_profile": True},
    "volume": {"ha_name": "volume"},
    "v40_min": {"ha_name": "v40_min"},
    "v40_level_min": {"ha_name": "v40_level_min"},
    "v40_level_max": {"ha_name": "v40_level_max"},
}
HEATER_MIN_TEMP = 10
HEATER_MAX_TEMP = 80
MANUFACTURER = "OSO Energy"

PLATFORMS = [
    Platform.WATER_HEATER,
]
PLATFORM_LOOKUP = {
    Platform.WATER_HEATER: "water_heater",
}
SERVICE_TURN_ON = "turn_on"
SERVICE_TURN_OFF = "turn_off"
SERVICE_SET_V40MIN = "set_v40_min"
SERVICE_SET_PROFILE = "set_profile"

TITLE = "OSO Energy"

OSO_ENERGY_TO_HASS_STATE = {
    "on": STATE_ON,
    "off": STATE_OFF,
}

OPERATION_LIST = [STATE_OFF, STATE_ON, STATE_PERFORMANCE]
