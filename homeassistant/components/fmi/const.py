"""Constants for the FMI Weather and Sensor integrations."""
from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "fmi"
NAME = "FMI"
MANUFACTURER = "Finnish Meteorological Institute"

COORDINATOR = "coordinator"
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)
MIN_TIME_BETWEEN_LIGHTNING_UPDATES = timedelta(minutes=60)
UNDO_UPDATE_LISTENER = "undo_update_listener"

FORECAST_OFFSET = [0, 1, 2, 3, 4, 6, 8, 12, 24]  # Based on API test runs
DEFAULT_NAME = "FMI"

ATTR_FORECAST = CONF_FORECAST = "forecast"
ATTR_HUMIDITY = "relative_humidity"
ATTR_WIND_SPEED = "wind_speed"
ATTR_PRECIPITATION = "precipitation"

ATTRIBUTION = "Weather Data provided by FMI"

# FMI Weather Visibility Constants
FMI_WEATHER_SYMBOL_MAP = {
    0: "clear-night",  # custom value 0 - not defined by FMI
    1: "sunny",  # "Clear",
    2: "partlycloudy",  # "Partially Clear",
    21: "rainy",  # "Light Showers",
    22: "pouring",  # "Showers",
    23: "pouring",  # "Strong Rain Showers",
    3: "cloudy",  # "Cloudy",
    31: "rainy",  # "Weak rains",
    32: "rainy",  # "Rains",
    33: "pouring",  # "Heavy Rains",
    41: "snowy-rainy",  # "Weak Snow",
    42: "cloudy",  # "Cloudy",
    43: "snowy",  # "Strong Snow",
    51: "snowy",  # "Light Snow",
    52: "snowy",  # "Snow",
    53: "snowy",  # "Heavy Snow",
    61: "lightning",  # "Thunderstorms",
    62: "lightning-rainy",  # "Strong Thunderstorms",
    63: "lightning",  # "Thunderstorms",
    64: "lightning-rainy",  # "Strong Thunderstorms",
    71: "rainy",  # "Weak Sleet",
    72: "rainy",  # "Sleet",
    73: "pouring",  # "Heavy Sleet",
    81: "rainy",  # "Light Sleet",
    82: "rainy",  # "Sleet",
    83: "pouring",  # "Heavy Sleet",
    91: "fog",  # "Fog",
    92: "fog",  # "Fog"
}
