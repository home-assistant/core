"""Constants for the Jellyfin integration tests."""

from typing import Final

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

TEST_URL: Final = "https://example.com"
TEST_NEW_URL: Final = "https://new.example.com"
TEST_USERNAME: Final = "test-username"
TEST_PASSWORD: Final = "test-password"

USER_INPUT: Final = {
    CONF_URL: TEST_URL,
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
}

REAUTH_INPUT: Final = {
    CONF_PASSWORD: TEST_PASSWORD,
}

RECONFIGURE_INPUT: Final = {
    CONF_URL: f"{TEST_NEW_URL}/",
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
}
