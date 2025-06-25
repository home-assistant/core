"""Constants for google_travel_time tests."""

from homeassistant.components.google_travel_time.const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_UNITS,
    UNITS_METRIC,
)
from homeassistant.const import CONF_API_KEY, CONF_MODE

MOCK_CONFIG = {
    CONF_API_KEY: "api_key",
    CONF_ORIGIN: "location1",
    CONF_DESTINATION: "49.983862755708444,8.223882827079068",
}

RECONFIGURE_CONFIG = {
    CONF_API_KEY: "api_key2",
    CONF_ORIGIN: "location3",
    CONF_DESTINATION: "location4",
}

DEFAULT_OPTIONS = {CONF_MODE: "driving", CONF_UNITS: UNITS_METRIC}
