"""Constants for Pterodactyl tests."""

from homeassistant.const import CONF_API_KEY, CONF_URL

TEST_URL = "https://192.168.0.1:8080/"

TEST_API_KEY = "TestClientApiKey"

TEST_USER_INPUT = {
    CONF_URL: TEST_URL,
    CONF_API_KEY: TEST_API_KEY,
}
