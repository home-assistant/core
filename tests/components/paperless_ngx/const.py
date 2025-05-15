"""Constants for the Paperless NGX integration tests."""

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

MOCK_CONFIG = {
    CONF_HOST: "http://paperless.example.com",
    CONF_ACCESS_TOKEN: "test_token",
}
