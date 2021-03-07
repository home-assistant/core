"""Constants for climacell tests."""

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

API_KEY = "aa"

MIN_CONFIG = {
    CONF_API_KEY: API_KEY,
}

V1_ENTRY_DATA = {
    CONF_NAME: "ClimaCell",
    CONF_API_KEY: API_KEY,
    CONF_LATITUDE: 80,
    CONF_LONGITUDE: 80,
}
