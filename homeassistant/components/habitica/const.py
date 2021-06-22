"""Constants for the habitica integration."""

from homeassistant.const import CONF_PATH, CONF_SERVICE_DATA

CONF_API_USER = "api_user"

DEFAULT_URL = "https://habitica.com"
DOMAIN = "habitica"

SERVICE_API_CALL = "api_call"
ATTR_PATH = CONF_PATH
ATTR_ARGS = "args"
ATTR_DATA = CONF_SERVICE_DATA
EVENT_API_CALL_SUCCESS = f"{DOMAIN}_{SERVICE_API_CALL}_success"
