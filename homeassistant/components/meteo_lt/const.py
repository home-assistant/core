"""Constants for the Meteo.lt integration."""

from datetime import timedelta

DOMAIN = "meteo_lt"

# API Configuration
API_BASE_URL = "https://api.meteo.lt/v1"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=30)

# Rate limiting (API allows 180 req/min, 20k/day)
API_TIMEOUT = 30

# Configuration
CONF_PLACE_CODE = "place_code"

# Attribution
ATTRIBUTION = "Data provided by Lithuanian Hydrometeorological Service (LHMT)"

# Platforms
PLATFORMS = ["weather"]

# Condition mapping from Meteo.lt to Home Assistant
CONDITION_MAP = {
    "clear": "sunny",
    "partly-cloudy": "partlycloudy",
    "cloudy-with-sunny-intervals": "partlycloudy",
    "cloudy": "cloudy",
    "light-rain": "rainy",
    "rain": "rainy",
    "heavy-rain": "pouring",
    "thunder": "lightning",
    "isolated-thunderstorms": "lightning-rainy",
    "thunderstorms": "lightning-rainy",
    "heavy-rain-with-thunderstorms": "lightning-rainy",
    "light-sleet": "snowy-rainy",
    "sleet": "snowy-rainy",
    "freezing-rain": "snowy-rainy",
    "hail": "hail",
    "light-snow": "snowy",
    "snow": "snowy",
    "heavy-snow": "snowy",
    "fog": "fog",
    "null": None,
}
