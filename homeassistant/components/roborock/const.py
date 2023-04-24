"""Constants for Roborock."""
from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"

PLATFORMS = [Platform.VACUUM, Platform.SENSOR]

# Total time in seconds consumables have before Roborock recommends replacing
MAIN_BRUSH_REPLACE_TIME = 1080000
SIDE_BRUSH_REPLACE_TIME = 720000
FILTER_REPLACE_TIME = 540000
SENSOR_DIRTY_REPLACE_TIME = 108000
