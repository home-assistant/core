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
    "weather": "rainy",
    "temperature": "7.9",
    "uv_index": "1",
    "probability_of_precipitation": "67",
    "pressure": "998.20",
    "wind_speed": "22.21",
    "wind_direction": "180",
    "wind_gust": "40.26",
    "feels_like_temperature": "3.4",
    "visibility_distance": "7478.00",
    "humidity": "97.5",
    "station_name": "King's Lynn",
}

WAVERTREE_SENSOR_RESULTS = {
    "weather": "rainy",
    "temperature": "9.3",
    "uv_index": "1",
    "probability_of_precipitation": "61",
    "pressure": "987.50",
    "wind_speed": "17.60",
    "wind_direction": "176",
    "wind_gust": "34.52",
    "feels_like_temperature": "5.8",
    "visibility_distance": "5106.00",
    "humidity": "95.13",
    "station_name": "Wavertree",
}

DEVICE_KEY_KINGSLYNN = {(DOMAIN, TEST_COORDINATES_KINGSLYNN)}
DEVICE_KEY_WAVERTREE = {(DOMAIN, TEST_COORDINATES_WAVERTREE)}
