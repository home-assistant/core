"""Constants for Roborock."""
from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"

PLATFORMS = [Platform.VACUUM, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
