"""Constants for the Hong Kong Observatory integration."""
from hko import LOCATIONS

DOMAIN = "hko"

DISTRICT = "name"

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

WEATHER_INFO_RAIN = "rain"
WEATHER_INFO_SNOW = "snow"
WEATHER_INFO_WIND = "wind"
WEATHER_INFO_MIST = "mist"
WEATHER_INFO_CLOUD = "cloud"
WEATHER_INFO_THUNDERSTORM = "thunderstorm"
WEATHER_INFO_SHOWER = "shower"
WEATHER_INFO_ISOLATED = "isolated"
WEATHER_INFO_HEAVY = "heavy"
WEATHER_INFO_SUNNY = "sunny"
WEATHER_INFO_FINE = "fine"
WEATHER_INFO_AT_TIMES_AT_FIRST = "at times at first"
WEATHER_INFO_OVERCAST = "overcast"
WEATHER_INFO_INTERVAL = "interval"
WEATHER_INFO_PERIOD = "period"
WEATHER_INFO_FOG = "FOG"
