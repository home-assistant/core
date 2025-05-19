"""Constants for the Paperless NGX integration tests."""

from homeassistant.const import CONF_API_KEY, CONF_HOST

USER_INPUT = {
    CONF_HOST: "192.168.69.16",
    CONF_API_KEY: "test_token",
}

PAPERLESS_IMPORT_PATHS = [
    "homeassistant.components.paperless_ngx.coordinator.Paperless",
    "homeassistant.components.paperless_ngx.config_flow.Paperless",
]

MOCK_REMOTE_VERSION_DATA = {"version": "2.3.0", "update_available": True}
