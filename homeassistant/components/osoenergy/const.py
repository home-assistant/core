"""Constants for OSO Energy."""
from homeassistant.components.water_heater import STATE_PERFORMANCE
from homeassistant.const import STATE_OFF, STATE_ON, Platform

ATTR_UNTIL_TEMP_LIMIT = "until_temp_limit"
ATTR_V40MIN = "v40_min"
ATTR_PROFILE_HOURS = {
    "00": "hour_00",
    "01": "hour_01",
    "02": "hour_02",
    "03": "hour_03",
    "04": "hour_04",
    "05": "hour_05",
    "06": "hour_06",
    "07": "hour_07",
    "08": "hour_08",
    "09": "hour_09",
    "10": "hour_10",
    "11": "hour_11",
    "12": "hour_12",
    "13": "hour_13",
    "14": "hour_14",
    "15": "hour_15",
    "16": "hour_16",
    "17": "hour_17",
    "18": "hour_18",
    "19": "hour_19",
    "20": "hour_20",
    "21": "hour_21",
    "22": "hour_22",
    "23": "hour_23",
}
CONFIG_ENTRY_VERSION = 1
DOMAIN = "osoenergy"

EXTRA_HEATER_ATTR = {
    "heater_state": "heater_state",
    "heater_mode": "heater_mode",
    "optimization_mode": "optimization_mode",
    "profile": "profile",
    "volume": "volume",
    "v40_min": "v40_min",
    "v40_level_min": "v40_level_min",
    "v40_level_max": "v40_level_max",
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
    "auto": "auto",
    "on": STATE_ON,
    "off": STATE_OFF,
    "manual": "manual",
    "legionella": "legionella",
    "powersave": "power_save",
    "extraenergy": "extra_energy",
    "voltage": "voltage",
    "ffr": "ffr",
    "oso": "oso",
    "gridcompany": "grid_company",
    "smartcompany": "smart_company",
    "advanced": "advanced",
}
OPERATION_LIST = [STATE_OFF, STATE_ON, STATE_PERFORMANCE]
