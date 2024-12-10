"""Helpers for testing Met Office DataPoint."""

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

TEST_DATETIME_STRING = "2024-11-23T12:00:00+00:00"

TEST_API_KEY = "test-metoffice-api-key"

TEST_LATITUDE_WAVERTREE = 53.38374
TEST_LONGITUDE_WAVERTREE = -2.90929
TEST_SITE_NAME_WAVERTREE = "Wavertree"

TEST_COORDINATES_WAVERTREE = f"{TEST_LATITUDE_WAVERTREE}_{TEST_LONGITUDE_WAVERTREE}"

TEST_LATITUDE_KINGSLYNN = 52.75556
TEST_LONGITUDE_KINGSLYNN = 0.44231
TEST_SITE_NAME_KINGSLYNN = "King's Lynn"

TEST_COORDINATES_KINGSLYNN = f"{TEST_LATITUDE_KINGSLYNN}_{TEST_LONGITUDE_KINGSLYNN}"

METOFFICE_CONFIG_WAVERTREE = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_LATITUDE: TEST_LATITUDE_WAVERTREE,
    CONF_LONGITUDE: TEST_LONGITUDE_WAVERTREE,
    CONF_NAME: TEST_SITE_NAME_WAVERTREE,
}

METOFFICE_CONFIG_KINGSLYNN = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_LATITUDE: TEST_LATITUDE_KINGSLYNN,
    CONF_LONGITUDE: TEST_LONGITUDE_KINGSLYNN,
    CONF_NAME: TEST_SITE_NAME_KINGSLYNN,
}

KINGSLYNN_SENSOR_RESULTS = {
    "significantWeatherCode": ("significantWeatherCode", "rainy"),
    "screenTemperature": ("screenTemperature", "7.87"),
    "uvIndex": ("uvIndex", "1"),
    "probOfPrecipitation": ("probOfPrecipitation", "67"),
    "mslp": ("mslp", "998.20"),
    "windSpeed10m": ("windSpeed10m", "22.21"),
}

WAVERTREE_SENSOR_RESULTS = {
    "significantWeatherCode": ("significantWeatherCode", "rainy"),
    "screenTemperature": ("screenTemperature", "9.28"),
    "uvIndex": ("uvIndex", "1"),
    "probOfPrecipitation": ("probOfPrecipitation", "61"),
    "mslp": ("mslp", "987.50"),
    "windSpeed10m": ("windSpeed10m", "17.60"),
}

DEVICE_KEY_KINGSLYNN = {(DOMAIN, TEST_COORDINATES_KINGSLYNN)}
DEVICE_KEY_WAVERTREE = {(DOMAIN, TEST_COORDINATES_WAVERTREE)}
