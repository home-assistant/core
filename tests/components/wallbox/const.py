"""Constants for wallbox tests."""
from homeassistant.components.wallbox.const import (
    CONF_STATION,
)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

# Mock config data to be used across multiple tests
MOCK_CONFIG = {
    CONF_USERNAME: "test_username",
    CONF_PASSWORD: "test_password",
    CONF_STATION: "12345",
}
