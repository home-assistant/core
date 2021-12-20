"""Android TV component constants."""
DOMAIN = "androidtv"

ANDROID_DEV = DOMAIN
ANDROID_DEV_OPT = "androidtv_opt"

CONF_ADB_SERVER_IP = "adb_server_ip"
CONF_ADB_SERVER_PORT = "adb_server_port"
CONF_ADBKEY = "adbkey"
CONF_APPS = "apps"
CONF_EXCLUDE_UNNAMED_APPS = "exclude_unnamed_apps"
CONF_GET_SOURCES = "get_sources"
CONF_MIGRATION_OPTIONS = "migration_options"
CONF_SCREENCAP = "screencap"
CONF_STATE_DETECTION_RULES = "state_detection_rules"
CONF_TURN_OFF_COMMAND = "turn_off_command"
CONF_TURN_ON_COMMAND = "turn_on_command"

DEFAULT_ADB_SERVER_PORT = 5037
DEFAULT_DEVICE_CLASS = "auto"
DEFAULT_EXCLUDE_UNNAMED_APPS = False
DEFAULT_GET_SOURCES = True
DEFAULT_PORT = 5555
DEFAULT_SCREENCAP = True

DEVICE_ANDROIDTV = "androidtv"
DEVICE_FIRETV = "firetv"
DEVICE_CLASSES = [DEFAULT_DEVICE_CLASS, DEVICE_ANDROIDTV, DEVICE_FIRETV]

PROP_ETHMAC = "ethmac"
PROP_SERIALNO = "serialno"
PROP_WIFIMAC = "wifimac"

SIGNAL_CONFIG_ENTITY = "androidtv_config"
