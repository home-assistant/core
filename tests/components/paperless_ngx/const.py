"""Constants for the Paperless NGX integration tests."""

from homeassistant.const import CONF_API_KEY, CONF_URL

USER_INPUT = {
    CONF_URL: "https://192.168.69.16:8000",
    CONF_API_KEY: "12345678",
}

USER_INPUT_UPDATE = {
    CONF_URL: "https://paperless.example.de",
    CONF_API_KEY: "87654321",
}
