"""Constants for Roborock."""
from homeassistant.const import Platform

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"

PLATFORMS = [Platform.VACUUM]

SERVICE_VACUUM_SET_MOP_MODE = "vacuum_set_mop_mode"
SERVICE_VACUUM_SET_MOP_INTENSITY = "vacuum_set_mop_intensity"
