"""Constants for WeatherKit."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Apple WeatherKit"
DOMAIN = "weatherkit"
ATTRIBUTION = (
    "Data provided by Apple Weather. "
    "https://developer.apple.com/weatherkit/data-source-attribution/"
)

MANUFACTURER = "Apple Weather"

CONF_KEY_ID = "key_id"
CONF_SERVICE_ID = "service_id"
CONF_TEAM_ID = "team_id"
CONF_KEY_PEM = "key_pem"

ATTR_CURRENT_WEATHER = "currentWeather"
ATTR_FORECAST_HOURLY = "forecastHourly"
ATTR_FORECAST_DAILY = "forecastDaily"
