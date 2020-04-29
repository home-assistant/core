"""Helpers for testing Met Office DataPoint."""

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

TEST_API_KEY = "test-metoffice-api-key"
TEST_LATITUDE = 53.38374
TEST_LONGITUDE = -2.90929

METOFFICE_CONFIG = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_LATITUDE: TEST_LATITUDE,
    CONF_LONGITUDE: TEST_LONGITUDE,
    CONF_NAME: "Wavertree",
}

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"
