"""Constants for the Control4 integration."""

from typing import Any

from homeassistant.config_entries import ConfigEntry

DOMAIN = "control4"

type Control4ConfigEntry = ConfigEntry[dict[str, Any]]

CONF_ACCOUNT = "account"
CONF_DIRECTOR = "director"
CONF_WEBSOCKET = "websocket"
CONF_CANCEL_TOKEN_REFRESH_CALLBACK = "cancel_token_refresh_callback"
CONF_DIRECTOR_SW_VERSION = "director_sw_version"
CONF_DIRECTOR_MODEL = "director_model"
CONF_DIRECTOR_ALL_ITEMS = "director_all_items"
CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"
CONF_UI_CONFIGURATION = "ui_configuration"

CONTROL4_ENTITY_TYPE = 7

RETRY_BACKOFF_MAX_SEC = 30
SCHEDULE_REFRESH_ADVANCE_SEC = 300

DEFAULT_SCAN_INTERVAL = 5
