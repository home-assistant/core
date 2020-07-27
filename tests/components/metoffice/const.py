"""Helpers for testing Met Office DataPoint."""

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"
TEST_DATETIME_STRING = "2020-04-25 12:00:00+0000"

TEST_API_KEY = "test-metoffice-api-key"

TEST_LATITUDE_WAVERTREE = 53.38374
TEST_LONGITUDE_WAVERTREE = -2.90929
TEST_SITE_NAME_WAVERTREE = "Wavertree"

TEST_LATITUDE_KINGSLYNN = 52.75556
TEST_LONGITUDE_KINGSLYNN = 0.44231
TEST_SITE_NAME_KINGSLYNN = "King's Lynn"

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
    "weather": ("weather", "sunny"),
    "visibility": ("visibility", "Very Good"),
    "visibility_distance": ("visibility_distance", "20-40"),
    "temperature": ("temperature", "14"),
    "feels_like_temperature": ("feels_like_temperature", "13"),
    "uv": ("uv_index", "6"),
    "precipitation": ("probability_of_precipitation", "0"),
    "wind_direction": ("wind_direction", "E"),
    "wind_gust": ("wind_gust", "7"),
    "wind_speed": ("wind_speed", "2"),
    "humidity": ("humidity", "60"),
}

WAVERTREE_SENSOR_RESULTS = {
    "weather": ("weather", "sunny"),
    "visibility": ("visibility", "Good"),
    "visibility_distance": ("visibility_distance", "10-20"),
    "temperature": ("temperature", "17"),
    "feels_like_temperature": ("feels_like_temperature", "14"),
    "uv": ("uv_index", "5"),
    "precipitation": ("probability_of_precipitation", "0"),
    "wind_direction": ("wind_direction", "SSE"),
    "wind_gust": ("wind_gust", "16"),
    "wind_speed": ("wind_speed", "9"),
    "humidity": ("humidity", "50"),
}
