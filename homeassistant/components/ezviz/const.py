"""Constants for the ezviz integration."""

DOMAIN = "ezviz"
MANUFACTURER = "EZVIZ"

# Configuration
ATTR_SERIAL = "serial"
CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"
ATTR_HOME = "HOME_MODE"
ATTR_AWAY = "AWAY_MODE"
ATTR_TYPE_CLOUD = "EZVIZ_CLOUD_ACCOUNT"
ATTR_TYPE_CAMERA = "CAMERA_ACCOUNT"

# Services data
DIR_UP = "up"
DIR_DOWN = "down"
DIR_LEFT = "left"
DIR_RIGHT = "right"
ATTR_ENABLE = "enable"
ATTR_DIRECTION = "direction"
ATTR_SPEED = "speed"
ATTR_LEVEL = "level"
ATTR_TYPE = "type_value"

# Service names
SERVICE_PTZ = "ptz"
SERVICE_ALARM_TRIGGER = "sound_alarm"
SERVICE_WAKE_DEVICE = "wake_device"
SERVICE_ALARM_SOUND = "alarm_sound"
SERVICE_DETECTION_SENSITIVITY = "set_alarm_detection_sensibility"

# Defaults
EU_URL = "apiieu.ezvizlife.com"
RUSSIA_URL = "apirus.ezvizru.com"
DEFAULT_CAMERA_USERNAME = "admin"
DEFAULT_RTSP_PORT = 554
DEFAULT_TIMEOUT = 25
DEFAULT_FFMPEG_ARGUMENTS = ""

# Data
DATA_COORDINATOR = "coordinator"
DATA_UNDO_UPDATE_LISTENER = "undo_update_listener"
