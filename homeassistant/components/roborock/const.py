"""Constants for Roborock."""
from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"
CONF_CACHED_INFORMATION = "cached_information"

PLATFORMS = [
    Platform.VACUUM,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.NUMBER,
]
