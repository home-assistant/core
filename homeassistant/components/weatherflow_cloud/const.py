"""Constants for the WeatherflowCloud integration."""

import logging

DOMAIN = "weatherflow_cloud"
LOGGER = logging.getLogger(__package__)

ATTR_ATTRIBUTION = "Weather data delivered by WeatherFlow/Tempest REST Api"
MANUFACTURER = "WeatherFlow"

STATE_MAP = {
    "clear-day": "sunny",
    "clear-night": "clear-night",
    "cloudy": "cloudy",
    "foggy": "fog",
    "partly-cloudy-day": "partlycloudy",
    "partly-cloudy-night": "partlycloudy",
    "possibly-rainy-day": "rainy",
    "possibly-rainy-night": "rainy",
    "possibly-sleet-day": "snowy-rainy",
    "possibly-sleet-night": "snowy-rainy",
    "possibly-snow-day": "snowy",
    "possibly-snow-night": "snowy",
    "possibly-thunderstorm-day": "lightning-rainy",
    "possibly-thunderstorm-night": "lightning-rainy",
    "rainy": "rainy",
    "sleet": "snowy-rainy",
    "snow": "snowy",
    "thunderstorm": "lightning",
    "windy": "windy",
}
