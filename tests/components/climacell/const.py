"""Constants for climacell tests."""

from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)

API_KEY = "aa"

API_V3_ENTRY_DATA = {
    CONF_NAME: "ClimaCell",
    CONF_API_KEY: API_KEY,
    CONF_LATITUDE: 80.0,
    CONF_LONGITUDE: 80.0,
    CONF_API_VERSION: 3,
}
