"""Constants for the FMD integration."""

DOMAIN = "fmd"

# Polling intervals (in minutes)
DEFAULT_POLLING_INTERVAL = 30
DEFAULT_HIGH_FREQUENCY_INTERVAL = 5

# Photo settings
DEFAULT_MAX_PHOTOS_TO_DOWNLOAD = 10
MEDIA_FOLDER_BASE = "fmd"  # Base folder under /media/ or /config/media/
# Photos stored in: /media/fmd/<device-id>/ or /config/media/fmd/<device-id>/

# Configuration keys
CONF_UPDATE_INTERVAL = "update_interval"
CONF_HIGH_FREQUENCY_INTERVAL = "high_frequency_interval"
CONF_HIGH_FREQUENCY_MODE = "high_frequency_mode"
CONF_ALLOW_INACCURATE = "allow_inaccurate"
CONF_USE_IMPERIAL = "use_imperial"

# Unit conversion constants
METERS_TO_FEET = 3.28084  # 1 meter = 3.28084 feet
MPS_TO_MPH = 2.23694  # 1 m/s = 2.23694 mph
