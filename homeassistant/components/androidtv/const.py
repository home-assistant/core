"""Android TV component constants."""

from typing import Final

DOMAIN: Final = "androidtv"

# Connection types
CONF_CONNECTION_TYPE: Final = "connection_type"
CONNECTION_TYPE_ADB: Final = "adb"
CONNECTION_TYPE_REMOTE: Final = "remote"

# ADB connection constants
CONF_ADB_SERVER_IP = "adb_server_ip"
CONF_ADB_SERVER_PORT = "adb_server_port"
CONF_ADBKEY = "adbkey"

# Remote protocol constants
CONF_ENABLE_IME: Final = "enable_ime"
CONF_ENABLE_IME_DEFAULT_VALUE: Final = True

# Common app configuration
CONF_APPS = "apps"
CONF_APP_NAME = "app_name"
CONF_APP_ICON = "app_icon"

# ADB-specific options
CONF_EXCLUDE_UNNAMED_APPS = "exclude_unnamed_apps"
CONF_GET_SOURCES = "get_sources"
CONF_SCREENCAP = "screencap"
CONF_SCREENCAP_INTERVAL = "screencap_interval"
CONF_STATE_DETECTION_RULES = "state_detection_rules"
CONF_TURN_OFF_COMMAND = "turn_off_command"
CONF_TURN_ON_COMMAND = "turn_on_command"

# Default values
DEFAULT_ADB_SERVER_PORT = 5037
DEFAULT_EXCLUDE_UNNAMED_APPS = False
DEFAULT_GET_SOURCES = True
DEFAULT_PORT = 5555
DEFAULT_SCREENCAP_INTERVAL = 5

# Device classes (for ADB connection)
DEVICE_AUTO = "auto"
DEVICE_ANDROIDTV = "androidtv"
DEVICE_FIRETV = "firetv"
DEVICE_CLASSES = {
    DEVICE_AUTO: "auto",
    DEVICE_ANDROIDTV: "Android TV",
    DEVICE_FIRETV: "Fire TV",
}

# Device property keys
PROP_ETHMAC = "ethmac"
PROP_SERIALNO = "serialno"
PROP_WIFIMAC = "wifimac"

# Signals
SIGNAL_CONFIG_ENTITY = "androidtv_config"
