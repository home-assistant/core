"""Constants for weenect tests."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

# Mock config data to be used across multiple tests
MOCK_CONFIG: dict[str, str] = {
    CONF_USERNAME: "test_username",
    CONF_PASSWORD: "test_password",
}
