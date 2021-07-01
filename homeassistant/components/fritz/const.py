"""Constants for the FRITZ!Box Tools integration."""

DOMAIN = "fritz"

PLATFORMS = ["binary_sensor", "device_tracker", "sensor", "switch"]

DATA_FRITZ = "fritz_data"

DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_HOST = "192.168.178.1"
DEFAULT_PORT = 49000
DEFAULT_USERNAME = ""

ERROR_AUTH_INVALID = "invalid_auth"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown_error"

FRITZ_SERVICES = "fritz_services"
SERVICE_REBOOT = "reboot"
SERVICE_RECONNECT = "reconnect"

SWITCH_PROFILE_STATUS_OFF = "never"
SWITCH_PROFILE_STATUS_ON = "unlimited"

SWITCH_TYPE_DEFLECTION = "CallDeflection"
SWITCH_TYPE_DEVICEPROFILE = "DeviceProfile"
SWITCH_TYPE_PORTFORWARD = "PortForward"
SWITCH_TYPE_WIFINETWORK = "WiFiNetwork"

TRACKER_SCAN_INTERVAL = 30

UPTIME_DEVIATION = 5
