"""iCloud component constants."""

DOMAIN = "icloud"
TRACKER_UPDATE = f"{DOMAIN}_tracker_update"

CONF_ACCOUNT_NAME = "account_name"
CONF_MAX_INTERVAL = "max_interval"
CONF_GPS_ACCURACY_THRESHOLD = "gps_accuracy_threshold"

DEFAULT_MAX_INTERVAL = 30  # min
DEFAULT_GPS_ACCURACY_THRESHOLD = 500  # meters

# Next PR will add sensor
ICLOUD_COMPONENTS = ["device_tracker"]
