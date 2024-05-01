"""Constants for the habitica integration."""

from homeassistant.const import CONF_PATH

CONF_API_USER = "api_user"

DEFAULT_URL = "https://habitica.com"
DOMAIN = "habitica"

# service constants
SERVICE_API_CALL = "api_call"
ATTR_PATH = CONF_PATH
ATTR_ARGS = "args"
ATTR_CONFIG_ENTRY = "config_entry"

MANUFACTURER = "HabitRPG, Inc."
NAME = "Habitica"
