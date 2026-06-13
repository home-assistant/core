"""Define constants for the Growatt Server component."""

from datetime import timedelta

from homeassistant.const import Platform

DEVICE_SCAN_INTERVAL = timedelta(hours=1)

CONF_PLANT_ID = "plant_id"

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

# Growatt Classic API error codes
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

# Internal key prefix for caching authenticated API instance
# Used to pass logged-in session from async_migrate_entry to async_setup_entry
# to avoid double login() calls that trigger API rate limiting
CACHED_API_KEY = "_cached_api_"

# Supported device types for coordinator creation
SUPPORTED_DEVICE_TYPES = ["inverter", "tlx", "storage", "mix", "min", "sph"]

# Maps V1 API device type integers to coordinator device-type strings
V1_DEVICE_TYPES: dict[int, str] = {5: "sph", 7: "min"}
