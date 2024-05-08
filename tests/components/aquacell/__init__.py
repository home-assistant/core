"""Tests for the Aquacell integration."""

from homeassistant.components.aquacell.const import CONF_REFRESH_TOKEN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

TEST_RESULT_DATA = {
    CONF_EMAIL: "test@test.com",
    CONF_PASSWORD: "test-password",
    CONF_REFRESH_TOKEN: "refresh-token",
}

TEST_USER_INPUT = {
    CONF_EMAIL: "test@test.com",
    CONF_PASSWORD: "test-password",
}
