"""Define constants for the Growatt Server component."""

from homeassistant.const import Platform

CONF_PLANT_ID = "plant_id"


# API key support
CONF_API_KEY = "api_key"

# Auth types for config flow
AUTH_PASSWORD = "password"
AUTH_API_TOKEN = "api_token"
CONF_AUTH_TYPE = "auth_type"
DEFAULT_AUTH_TYPE = AUTH_PASSWORD

DEFAULT_PLANT_ID = "0"

DEFAULT_NAME = "Growatt"

SERVER_URLS = [
    "https://openapi.growatt.com/",  # Other regional server
    "https://openapi-cn.growatt.com/",  # Chinese server
    "https://openapi-us.growatt.com/",  # North American server
    "https://openapi-au.growatt.com/",  # Australia Server
    "http://server.smten.com/",  # smten server
]

DEPRECATED_URLS = [
    "https://server.growatt.com/",
    "https://server-api.growatt.com/",
    "https://server-us.growatt.com/",
]

DEFAULT_URL = SERVER_URLS[0]

DOMAIN = "growatt_server"

PLATFORMS = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

LOGIN_INVALID_AUTH_CODE = "502"

# Config flow error types (also used as abort reasons)
ERROR_CANNOT_CONNECT = "cannot_connect"  # Used for both form errors and aborts
ERROR_INVALID_AUTH = "invalid_auth"

# Config flow abort reasons
ABORT_NO_PLANTS = "no_plants"
