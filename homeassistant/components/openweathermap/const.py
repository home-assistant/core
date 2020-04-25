"""Consts for the OpenWeatherMap."""
DOMAIN = "openweathermap"
DEFAULT_NAME = "OpenWeatherMap"
DEFAULT_LANGUAGE = "en"
DEFAULT_FORECAST_MODE = "hourly"
ATTRIBUTION = "Data provided by OpenWeatherMap"
CONF_LANGUAGE = "language"
ENTRY_NAME = "name"
ENTRY_FORECAST_COORDINATOR = "forecast_coordinator"
ENTRY_WEATHER_COORDINATOR = "weather_coordinator"
ENTRY_MONITORED_CONDITIONS = "monitored_conditions"
ATTR_API_WEATHER = "weather"
ATTR_API_TEMPERATURE = "temperature"
ATTR_API_WIND_SPEED = "wind_speed"
ATTR_API_WIND_BEARING = "wind_bearing"
ATTR_API_HUMIDITY = "humidity"
ATTR_API_PRESSURE = "pressure"
ATTR_API_CONDITION = "condition"
ATTR_API_CLOUDS = "clouds"
ATTR_API_RAIN = "rain"
ATTR_API_SNOW = "snow"
ATTR_API_WEATHER_CODE = "weather_code"
ATTR_API_FORECAST = "forecast"
SENSOR_NAME = "sensor_name"
SENSOR_UNIT = "sensor_unit"
SENSOR_DEVICE_CLASS = "sensor_device_class"
COMPONENTS = ["sensor", "weather"]
FORECAST_MODES = ["hourly", "daily", "freedaily"]
# weather,temperature,wind_speed,wind_bearing,humidity,pressure,clouds,rain,snow,weather_code
MONITORED_CONDITIONS = [
    ATTR_API_WEATHER,
    ATTR_API_TEMPERATURE,
    ATTR_API_WIND_SPEED,
    ATTR_API_WIND_BEARING,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_CLOUDS,
    ATTR_API_RAIN,
    ATTR_API_SNOW,
    ATTR_API_WEATHER_CODE,
]
LANGUAGES = ["en", "es", "ru", "it"]
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
