"""Constants for the Paperless NGX integration tests."""

from homeassistant.const import CONF_API_KEY, CONF_URL

USER_INPUT_ONE = {
    CONF_URL: "https://192.168.69.16:8000",
    CONF_API_KEY: "12345678",
}

USER_INPUT_TWO = {
    CONF_URL: "https://paperless.example.de",
    CONF_API_KEY: "87654321",
}

USER_INPUT_REAUTH = {CONF_API_KEY: "192837465"}
