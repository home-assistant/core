"""Constants for the Hong Kong Observatory integration."""
from hko import LOCATIONS

DOMAIN = "hko"

DISTRICT = "name"
COORDINATOR = "coordinator"
UPDATE_LISTENER = "update_listener"

KEY_LOCATION = "LOCATION"
KEY_DISTRICT = "DISTRICT"

DEFAULT_LOCATION = LOCATIONS[0][KEY_LOCATION]
DEFAULT_DISTRICT = LOCATIONS[0][KEY_DISTRICT]

MANUFACTURER = "Hong Kong Observatory"
ATTRIBUTION = "Data provided by Hong Kong Observatory"

API_CURRENT = "current"
API_FORECAST = "forecast"
API_WEATHER_FORECAST = "weatherForecast"
API_FORECAST_DATE = "forecastDate"
API_FORECAST_ICON = "ForecastIcon"
API_FORECAST_WEATHER = "forecastWeather"
API_FORECAST_MAX_TEMP = "forecastMaxtemp"
API_FORECAST_MIN_TEMP = "forecastMintemp"
API_CONDITION = "condition"
API_TEMPERATURE = "temperature"
API_HUMIDITY = "humidity"
API_PLACE = "place"
API_DATA = "data"
API_VALUE = "value"
