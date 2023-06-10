"""Constants for buienradar component."""

DOMAIN = "buienradar"

DEFAULT_TIMEFRAME = 60

DEFAULT_DIMENSION = 700
DEFAULT_DELTA = 600

CONF_DELTA = "delta"
CONF_COUNTRY = "country_code"
CONF_TIMEFRAME = "timeframe"

SUPPORTED_COUNTRY_CODES = ["NL", "BE"]
DEFAULT_COUNTRY = "NL"

"""Schedule next call after (minutes)."""
SCHEDULE_OK = 10
"""When an error occurred, new call after (minutes)."""
SCHEDULE_NOK = 2

STATE_CONDITIONS = ["clear", "cloudy", "fog", "rainy", "snowy", "lightning"]

STATE_DETAILED_CONDITIONS = [
    "clear",
    "partlycloudy",
    "partlycloudy-fog",
    "partlycloudy-light-rain",
    "partlycloudy-rain",
    "cloudy",
    "fog",
    "rainy",
    "light-rain",
    "light-snow",
    "partlycloudy-light-snow",
    "partlycloudy-snow",
    "partlycloudy-lightning",
    "snowy",
    "snowy-rainy",
    "lightning",
]

STATE_CONDITION_CODES = [
    "a",
    "b",
    "j",
    "o",
    "r",
    "c",
    "p",
    "d",
    "n",
    "f",
    "h",
    "k",
    "l",
    "q",
    "w",
    "m",
    "u",
    "i",
    "v",
    "t",
    "g",
    "s",
]
