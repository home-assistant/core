"""Constants for the elmax-cloud integration."""
from homeassistant.const import Platform

DOMAIN = "elmax"
CONF_ELMAX_USERNAME = "username"
CONF_ELMAX_PASSWORD = "password"
CONF_ELMAX_PANEL_ID = "panel_id"
CONF_ELMAX_PANEL_PIN = "panel_pin"
CONF_ELMAX_PANEL_NAME = "panel_name"

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_ENDPOINT_ID = "endpoint_id"

ELMAX_PLATFORMS = [Platform.SWITCH]

POLLING_SECONDS = 30
DEFAULT_TIMEOUT = 10.0
