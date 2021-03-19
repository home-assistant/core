"""Constants for wallbox tests."""
from homeassistant.components.wallbox.const import CONF_STATION
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

# Mock config data to be used across multiple tests
MOCK_CONFIG = {
    CONF_USERNAME: "test_username",
    CONF_PASSWORD: "test_password",
    CONF_STATION: "12345",
}
