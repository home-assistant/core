"""Constants for the ecobee integration."""

import logging

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)
from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN = "ecobee"
ATTR_AVAILABLE_SENSORS = "available_sensors"
ATTR_ACTIVE_SENSORS = "active_sensors"

CONF_REFRESH_TOKEN = "refresh_token"

ECOBEE_MODEL_TO_NAME = {
    "idtSmart": "ecobee Smart",
    "idtEms": "ecobee Smart EMS",
    "siSmart": "ecobee Si Smart",
    "siEms": "ecobee Si EMS",
    "athenaSmart": "ecobee3 Smart",
    "athenaEms": "ecobee3 EMS",
    "corSmart": "Carrier/Bryant Cor",
    "nikeSmart": "ecobee3 lite Smart",
    "nikeEms": "ecobee3 lite EMS",
    "apolloSmart": "ecobee4 Smart",
    "vulcanSmart": "ecobee4 Smart",
    "aresSmart": "ecobee Smart Premium",
    "artemisSmart": "ecobee Smart Enhanced",
    "attisRetail": "ecobee Smart Thermostat with Voice Control",
    "attisPro": "ecobee Smart Thermostat Lite",
}

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.HUMIDIFIER,
    Platform.NOTIFY,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WEATHER,
]

MANUFACTURER = "ecobee"

ECOBEE_AUX_HEAT_ONLY = "auxHeatOnly"

# Maps ecobee's notificationSettings.equipment[].type to the alertNumber
# that fires when the reminder is due.
# See ecobee API docs, Alert Object.
ECOBEE_EQUIPMENT_TYPE_TO_ALERT_NUMBER: dict[str, int] = {
    "hvac": 3140,
    "furnaceFilter": 3130,
    "humidifierFilter": 3131,
    "dehumidifierFilter": 3133,
    "ventilator": 3132,
    "economizer": 3134,
    "ac": 3136,
    "airFilter": 3137,
    "airCleaner": 3138,
    "uvLamp": 3135,
}

# Maps alertNumber to the translation key used in strings.json.
ECOBEE_ALERT_NUMBER_TO_TRANSLATION_KEY: dict[int, str] = {
    3130: "furnace_filter_reminder",
    3131: "humidifier_filter_reminder",
    3132: "ventilator_reminder",
    3133: "dehumidifier_filter_reminder",
    3134: "economizer_reminder",
    3135: "uv_lamp_reminder",
    3136: "ac_maintenance_reminder",
    3137: "air_filter_reminder",
    3138: "air_cleaner_reminder",
    3140: "hvac_maintenance_reminder",
}

# Translates ecobee API weatherSymbol to Home Assistant usable names
# https://www.ecobee.com/home/developer/api/documentation/v1/objects/WeatherForecast.shtml
ECOBEE_WEATHER_SYMBOL_TO_HASS = {
    0: ATTR_CONDITION_SUNNY,
    1: ATTR_CONDITION_PARTLYCLOUDY,
    2: ATTR_CONDITION_PARTLYCLOUDY,
    3: ATTR_CONDITION_CLOUDY,
    4: ATTR_CONDITION_CLOUDY,
    5: ATTR_CONDITION_CLOUDY,
    6: ATTR_CONDITION_RAINY,
    7: ATTR_CONDITION_SNOWY_RAINY,
    8: ATTR_CONDITION_POURING,
    9: ATTR_CONDITION_HAIL,
    10: ATTR_CONDITION_SNOWY,
    11: ATTR_CONDITION_SNOWY,
    12: ATTR_CONDITION_SNOWY_RAINY,
    13: "snowy-heavy",
    14: ATTR_CONDITION_HAIL,
    15: ATTR_CONDITION_LIGHTNING_RAINY,
    16: ATTR_CONDITION_WINDY,
    17: "tornado",
    18: ATTR_CONDITION_FOG,
    19: "hazy",
    20: "hazy",
    21: "hazy",
    -2: None,
}
