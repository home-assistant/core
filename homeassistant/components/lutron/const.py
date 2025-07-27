"""Lutron constants."""

DOMAIN = "lutron"

# Configuration keys
CONF_REFRESH_DATA = "refresh_data"
CONF_USE_FULL_PATH = "use_full_path"
CONF_USE_AREA_FOR_DEVICE_NAME = "use_area_for_device_name"
CONF_VARIABLE_IDS = "variable_ids"
CONF_USE_RADIORA_MODE = "use_radiora_mode"

# Connection settings
CONF_CONNECTION_TIMEOUT = "connection_timeout"
CONF_RETRY_ATTEMPTS = "retry_attempts"
CONF_RETRY_DELAY = "retry_delay"
CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"
CONF_DEBUG_MODE = "debug_mode"

# File paths
LUTRON_DATA_FILE = "lutron_data.xml"

# Device settings
CONF_DEFAULT_DIMMER_LEVEL = "default_dimmer_level"

# Default values
DEFAULT_DIMMER_LEVEL = 255
DEFAULT_CONNECTION_TIMEOUT = 30
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 5.0
DEFAULT_HEARTBEAT_INTERVAL = 60
DEFAULT_DEBUG_MODE = False

# Connection states
CONNECTION_STATE_CONNECTED = "connected"
CONNECTION_STATE_DISCONNECTED = "disconnected"
CONNECTION_STATE_CONNECTING = "connecting"

# Device types
DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_COVER = "cover"
DEVICE_TYPE_FAN = "fan"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_KEYPAD = "keypad"
DEVICE_TYPE_BUTTON = "button"
DEVICE_TYPE_LED = "led"
DEVICE_TYPE_SENSOR = "sensor"
DEVICE_TYPE_VARIABLE = "variable"

# Error messages
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_TIMEOUT = "timeout"
ERROR_UNKNOWN = "unknown"
ERROR_DATABASE_LOAD = "database_load"
ERROR_DEVICE_NOT_FOUND = "device_not_found"
