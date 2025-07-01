"""Consts for the OpenWeatherMap."""

from __future__ import annotations

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.const import Platform

DOMAIN = "openweathermap"
DEFAULT_NAME = "OpenWeatherMap"
DEFAULT_LANGUAGE = "en"
ATTRIBUTION = "Data provided by OpenWeatherMap"
MANUFACTURER = "OpenWeather"
CONFIG_FLOW_VERSION = 5
ATTR_API_PRECIPITATION = "precipitation"
ATTR_API_PRECIPITATION_KIND = "precipitation_kind"
ATTR_API_DATETIME = "datetime"
ATTR_API_DEW_POINT = "dew_point"
ATTR_API_WEATHER = "weather"
ATTR_API_TEMPERATURE = "temperature"
ATTR_API_FEELS_LIKE_TEMPERATURE = "feels_like_temperature"
ATTR_API_WIND_GUST = "wind_gust"
ATTR_API_WIND_SPEED = "wind_speed"
ATTR_API_WIND_BEARING = "wind_bearing"
ATTR_API_HUMIDITY = "humidity"
ATTR_API_PRESSURE = "pressure"
ATTR_API_CONDITION = "condition"
ATTR_API_CLOUDS = "clouds"
ATTR_API_RAIN = "rain"
ATTR_API_SNOW = "snow"
ATTR_API_UV_INDEX = "uv_index"
ATTR_API_VISIBILITY_DISTANCE = "visibility_distance"
ATTR_API_WEATHER_CODE = "weather_code"
ATTR_API_CLOUD_COVERAGE = "cloud_coverage"
ATTR_API_FORECAST = "forecast"
ATTR_API_CURRENT = "current"
ATTR_API_MINUTE_FORECAST = "minute_forecast"
ATTR_API_HOURLY_FORECAST = "hourly_forecast"
ATTR_API_DAILY_FORECAST = "daily_forecast"
ATTR_API_AIRPOLLUTION_AQI = "aqi"
ATTR_API_AIRPOLLUTION_CO = "co"
ATTR_API_AIRPOLLUTION_NO = "no"
ATTR_API_AIRPOLLUTION_NO2 = "no2"
ATTR_API_AIRPOLLUTION_O3 = "o3"
ATTR_API_AIRPOLLUTION_SO2 = "so2"
ATTR_API_AIRPOLLUTION_PM2_5 = "pm2_5"
ATTR_API_AIRPOLLUTION_PM10 = "pm10"
ATTR_API_AIRPOLLUTION_NH3 = "nh3"

UPDATE_LISTENER = "update_listener"
PLATFORMS = [Platform.SENSOR, Platform.WEATHER]

OWM_MODE_FREE_CURRENT = "current"
OWM_MODE_FREE_FORECAST = "forecast"
OWM_MODE_V30 = "v3.0"
OWM_MODE_AIRPOLLUTION = "air_pollution"
OWM_MODES = [
    OWM_MODE_V30,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_AIRPOLLUTION,
]
DEFAULT_OWM_MODE = OWM_MODE_V30

LANGUAGES = [
    "af",
    "al",
    "ar",
    "az",
    "bg",
    "ca",
    "cz",
    "da",
    "de",
    "el",
    "en",
    "es",
    "eu",
    "fa",
    "fi",
    "fr",
    "gl",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "kr",
    "la",
    "lt",
    "mk",
    "nl",
    "no",
    "pl",
    "pt",
    "pt_br",
    "ro",
    "ru",
    "se",
    "sk",
    "sl",
    "sp",
    "sr",
    "sv",
    "th",
    "tr",
    "ua",
    "uk",
    "vi",
    "zh_cn",
    "zh_tw",
    "zu",
]
WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT = 800
CONDITION_CLASSES = {
    ATTR_CONDITION_CLOUDY: [803, 804],
    ATTR_CONDITION_FOG: [701, 721, 741],
    ATTR_CONDITION_HAIL: [906],
    ATTR_CONDITION_LIGHTNING: [210, 211, 212, 221],
    ATTR_CONDITION_LIGHTNING_RAINY: [200, 201, 202, 230, 231, 232],
    ATTR_CONDITION_PARTLYCLOUDY: [801, 802],
    ATTR_CONDITION_POURING: [504, 314, 502, 503, 522],
    ATTR_CONDITION_RAINY: [300, 301, 302, 310, 311, 312, 313, 500, 501, 520, 521],
    ATTR_CONDITION_SNOWY: [600, 601, 602, 611, 612, 620, 621, 622],
    ATTR_CONDITION_SNOWY_RAINY: [511, 615, 616],
    ATTR_CONDITION_SUNNY: [WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT],
    ATTR_CONDITION_WINDY: [905, 951, 952, 953, 954, 955, 956, 957],
    ATTR_CONDITION_WINDY_VARIANT: [958, 959, 960, 961],
    ATTR_CONDITION_EXCEPTIONAL: [
        711,
        731,
        751,
        761,
        762,
        771,
        900,
        901,
        962,
        903,
        904,
    ],
}
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}
