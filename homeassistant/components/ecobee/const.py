"""Constants for the ecobee integration."""
import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "ecobee"
DATA_ECOBEE_CONFIG = "ecobee_config"

CONF_INDEX = "index"
CONF_REFRESH_TOKEN = "refresh_token"

ATTR_COOL_TEMP = "cool_temp"
ATTR_END_DATE = "end_date"
ATTR_END_TIME = "end_time"
ATTR_FAN_MIN_ON_TIME = "fan_min_on_time"
ATTR_FAN_MODE = "fan_mode"
ATTR_HEAT_TEMP = "heat_temp"
ATTR_RESUME_ALL = "resume_all"
ATTR_START_DATE = "start_date"
ATTR_START_TIME = "start_time"
ATTR_VACATION_NAME = "vacation_name"
DEFAULT_RESUME_ALL = False
PRESET_HOLD_NEXT_TRANSITION = "next_transition"
PRESET_HOLD_INDEFINITE = "indefinite"
PRESET_TEMPERATURE = "temp"
PRESET_VACATION = "vacation"

ECOBEE_INVALID_TOKEN_MESSAGE = (
    "Your ecobee credentials have expired; "
    "please remove and re-add the integration to re-authenticate"
)

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
