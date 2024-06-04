"""Constants for google_travel_time tests."""

from homeassistant.components.google_travel_time.const import (
    CONF_DESTINATION,
    CONF_ORIGIN,
)
from homeassistant.const import CONF_API_KEY

MOCK_CONFIG = {
    CONF_API_KEY: "api_key",
    CONF_ORIGIN: "location1",
    CONF_DESTINATION: "location2",
}
