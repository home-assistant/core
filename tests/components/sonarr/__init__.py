"""Tests for the Sonarr component."""
from homeassistant.components.sonarr.const import CONF_BASE_PATH
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL

MOCK_REAUTH_INPUT = {CONF_API_KEY: "test-api-key-reauth"}

MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.189",
    CONF_PORT: 8989,
    CONF_BASE_PATH: "/api",
    CONF_SSL: False,
    CONF_API_KEY: "MOCK_API_KEY",
}
