"""Constants for the FRITZ!Box Tools integration."""

DOMAIN = "fritz"

PLATFORMS = ["binary_sensor", "device_tracker", "sensor"]

DATA_FRITZ = "fritz_data"

DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_HOST = "192.168.178.1"
DEFAULT_PORT = 49000
DEFAULT_USERNAME = ""


ERROR_AUTH_INVALID = "invalid_auth"
ERROR_CONNECTION_ERROR = "connection_error"
ERROR_UNKNOWN = "unknown_error"

TRACKER_SCAN_INTERVAL = 30

UPTIME_DEVIATION = 5
