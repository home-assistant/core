"""Constants for the ecobee integration."""
import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "ecobee"
DATA_ECOBEE_CONFIG = "ecobee_config"

CONF_INDEX = "index"
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
}

ECOBEE_PLATFORMS = ["binary_sensor", "climate", "sensor", "weather"]

MANUFACTURER = "ecobee"

# Translates ecobee API weatherSymbol to Home Assistant usable names
# https://www.ecobee.com/home/developer/api/documentation/v1/objects/WeatherForecast.shtml
ECOBEE_WEATHER_SYMBOL_TO_HASS = {
    0: "sunny",
    1: "partlycloudy",
    2: "partlycloudy",
    3: "cloudy",
    4: "cloudy",
    5: "cloudy",
    6: "rainy",
    7: "snowy-rainy",
    8: "pouring",
    9: "hail",
    10: "snowy",
    11: "snowy",
    12: "snowy-rainy",
    13: "snowy-heavy",
    14: "hail",
    15: "lightning-rainy",
    16: "windy",
    17: "tornado",
    18: "fog",
    19: "hazy",
    20: "hazy",
    21: "hazy",
    -2: None,
}
