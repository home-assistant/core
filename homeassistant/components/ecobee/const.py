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

_LOGGER = logging.getLogger(__package__)

DOMAIN = "ecobee"
DATA_ECOBEE_CONFIG = "ecobee_config"
DATA_HASS_CONFIG = "ecobee_hass_config"
ATTR_CONFIG_ENTRY_ID = "entry_id"
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
