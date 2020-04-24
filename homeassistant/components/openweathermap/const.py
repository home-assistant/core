"""Consts for the OpenWeatherMap."""
from homeassistant.const import SPEED_METERS_PER_SECOND, UNIT_DEGREE, UNIT_PERCENTAGE

DOMAIN = "openweathermap"
DEFAULT_NAME = "OpenWeatherMap"
DEFAULT_LANGUAGE = "en"
DEFAULT_FORECAST_MODE = "hourly"
ATTRIBUTION = "Data provided by OpenWeatherMap"
CONF_FORECAST = "forecast"
CONF_LANGUAGE = "language"
ENTITY_NAME = "entity_name"
FORECAST_COORDINATOR = "forecast_coordinator"
WEATHER_COORDINATOR = "weather_coordinator"
MONITORED_CONDITIONS = "monitored_conditions"
ATTR_API_WEATHER = "WEATHER"
ATTR_API_TEMP = "TEMP"
ATTR_API_PRESSURE = "PRESSURE"
ATTR_API_HUMIDITY = "HUMIDITY"
ATTR_API_CONDITION = "CONDITION"
ATTR_API_WIND_BEARING = "WIND_BEARING"
ATTR_API_WIND_SPEED = "WIND_SPEED"
ATTR_API_CLOUDS = "CLOUDS"
ATTR_API_WEATHER_CODE = "WEATHER_CODE"
ATTR_API_FORECAST = "FORECAST"
COMPONENTS = ["sensor", "weather"]
FORECAST_MODE = ["hourly", "daily", "freedaily"]
SENSOR_TYPES = {
    "weather": ["Condition", None, ATTR_API_WEATHER],
    "temperature": ["Temperature", None, ATTR_API_TEMP],
    "wind_speed": ["Wind speed", SPEED_METERS_PER_SECOND, ATTR_API_WIND_SPEED],
    "wind_bearing": ["Wind bearing", UNIT_DEGREE, ATTR_API_WIND_BEARING],
    "humidity": ["Humidity", UNIT_PERCENTAGE, ATTR_API_HUMIDITY],
    "pressure": ["Pressure", "mbar", ATTR_API_PRESSURE],
    "clouds": ["Cloud coverage", UNIT_PERCENTAGE, ATTR_API_CLOUDS],
    "rain": ["Rain", "mm", None],
    "snow": ["Snow", "mm", None],
    "weather_code": ["Weather code", None, ATTR_API_WEATHER_CODE],
}
CONDITION_CLASSES = {
    "cloudy": [803, 804],
    "fog": [701, 741],
    "hail": [906],
    "lightning": [210, 211, 212, 221],
    "lightning-rainy": [200, 201, 202, 230, 231, 232],
    "partlycloudy": [801, 802],
    "pouring": [504, 314, 502, 503, 522],
    "rainy": [300, 301, 302, 310, 311, 312, 313, 500, 501, 520, 521],
    "snowy": [600, 601, 602, 611, 612, 620, 621, 622],
    "snowy-rainy": [511, 615, 616],
    "sunny": [800],
    "windy": [905, 951, 952, 953, 954, 955, 956, 957],
    "windy-variant": [958, 959, 960, 961],
    "exceptional": [711, 721, 731, 751, 761, 762, 771, 900, 901, 962, 903, 904],
}
