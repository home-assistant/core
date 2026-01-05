"""Define constants for the Growatt Server component."""

from homeassistant.const import Platform

CONF_PLANT_ID = "plant_id"
CONF_REGION = "region"


# API key support
CONF_API_KEY = "api_key"

# Auth types for config flow
AUTH_PASSWORD = "password"
AUTH_API_TOKEN = "api_token"
CONF_AUTH_TYPE = "auth_type"
DEFAULT_AUTH_TYPE = AUTH_PASSWORD

DEFAULT_PLANT_ID = "0"

DEFAULT_NAME = "Growatt"

SERVER_URLS_NAMES = {
    "north_america": "https://openapi-us.growatt.com/",
    "australia_new_zealand": "https://openapi-au.growatt.com/",
    "china": "https://openapi-cn.growatt.com/",
    "other_regions": "https://openapi.growatt.com/",
    "smten_server": "http://server.smten.com/",
    "era_server": "http://ess-server.atesspower.com/",
}

DEPRECATED_URLS = [
    "https://server.growatt.com/",
    "https://server-api.growatt.com/",
    "https://server-us.growatt.com/",
]

DEFAULT_URL = "other_regions"

DOMAIN = "growatt_server"

PLATFORMS = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

LOGIN_INVALID_AUTH_CODE = "502"

# Config flow error types (also used as abort reasons)
ERROR_CANNOT_CONNECT = "cannot_connect"  # Used for both form errors and aborts
ERROR_INVALID_AUTH = "invalid_auth"

# Config flow abort reasons
ABORT_NO_PLANTS = "no_plants"

# Battery modes for TOU (Time of Use) settings
BATT_MODE_LOAD_FIRST = 0
BATT_MODE_BATTERY_FIRST = 1
BATT_MODE_GRID_FIRST = 2
