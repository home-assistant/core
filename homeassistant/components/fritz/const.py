"""Constants for the FRITZ!Box Tools integration."""

DOMAIN = "fritz"

PLATFORMS = ["binary_sensor", "device_tracker", "sensor"]

CONF_ADD_ALL_TRACKER = "add_all_tracker"
CONF_ADD_NEW_TRACKER = "add_new_tracker"
CONF_SELECTED_DEVICES = "selected_devices"

DATA_ACTIVE_TRACKER = "active_tracker"
DATA_KNOWN_DEVICES = "known_devices"

DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_HOST = "192.168.178.1"
DEFAULT_PORT = 49000
DEFAULT_USERNAME = ""
DEFAULT_ADD_ALL_TRACKER = False
DEFAULT_ADD_NEW_TRACKER = False

ERROR_AUTH_INVALID = "invalid_auth"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown_error"

FRITZ_SERVICES = "fritz_services"
FRITZ_TOOLS = "fritz_tools"
SERVICE_REBOOT = "reboot"
SERVICE_RECONNECT = "reconnect"
UNDO_UPDATE_LISTENER_OPTIONS = "update_listner_options"
UNDO_UPDATE_LISTENER_TRACKER = "update_listner_tracker"

TRACKER_SCAN_INTERVAL = 30

UPTIME_DEVIATION = 5
