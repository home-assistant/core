"""Tests for the Sonarr component."""
from homeassistant.const import CONF_API_KEY, CONF_URL

MOCK_REAUTH_INPUT = {CONF_API_KEY: "test-api-key-reauth"}

MOCK_USER_INPUT = {
    CONF_URL: "http://192.168.1.189:8989",
    CONF_API_KEY: "MOCK_API_KEY",
}
