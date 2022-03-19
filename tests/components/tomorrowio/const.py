"""Constants for tomorrowio tests."""

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE

API_KEY = "aa"

MIN_CONFIG = {
    CONF_API_KEY: API_KEY,
}

V1_ENTRY_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_LATITUDE: 80,
    CONF_LONGITUDE: 80,
}

API_V4_ENTRY_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_LATITUDE: 80,
    CONF_LONGITUDE: 80,
}
