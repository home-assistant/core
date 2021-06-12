"""Constants for the Zyxel T-50 integration."""

DOMAIN = "zyxelt50"

PLATFORMS = ["device_tracker"]
# PLATFORMS = ["binary_sensor", "device_tracker", "sensor"]

DATA_ZYXEL = "zyxel_data"

DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_HOST = "192.168.1.1"
DEFAULT_USERNAME = "admin"

ERROR_AUTH_INVALID = "invalid_auth"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown_error"

TRACKER_SCAN_INTERVAL = 30

UPTIME_DEVIATION = 5
