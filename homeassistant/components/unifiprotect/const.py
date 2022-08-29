"""Constant definitions for UniFi Protect Integration."""

from pyunifiprotect.data import ModelType, Version

from homeassistant.const import Platform

DOMAIN = "unifiprotect"

ATTR_EVENT_SCORE = "event_score"
ATTR_WIDTH = "width"
ATTR_HEIGHT = "height"
ATTR_FPS = "fps"
ATTR_BITRATE = "bitrate"
ATTR_CHANNEL_ID = "channel_id"
ATTR_MESSAGE = "message"
ATTR_DURATION = "duration"
ATTR_ANONYMIZE = "anonymize"

CONF_DISABLE_RTSP = "disable_rtsp"
CONF_ALL_UPDATES = "all_updates"
CONF_OVERRIDE_CHOST = "override_connection_host"
CONF_MAX_MEDIA = "max_media"

CONFIG_OPTIONS = [
    CONF_ALL_UPDATES,
    CONF_DISABLE_RTSP,
    CONF_OVERRIDE_CHOST,
]

DEFAULT_PORT = 443
DEFAULT_ATTRIBUTION = "Powered by UniFi Protect Server"
DEFAULT_BRAND = "Ubiquiti"
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_VERIFY_SSL = False
DEFAULT_MAX_MEDIA = 1000

DEVICES_THAT_ADOPT = {
    ModelType.CAMERA,
    ModelType.LIGHT,
    ModelType.VIEWPORT,
    ModelType.SENSOR,
    ModelType.DOORLOCK,
    ModelType.CHIME,
}
DEVICES_WITH_ENTITIES = DEVICES_THAT_ADOPT | {ModelType.NVR}
DEVICES_FOR_SUBSCRIBE = DEVICES_WITH_ENTITIES | {ModelType.EVENT}

MIN_REQUIRED_PROTECT_V = Version("1.20.0")
OUTDATED_LOG_MESSAGE = "You are running v%s of UniFi Protect. Minimum required version is v%s. Please upgrade UniFi Protect and then retry"

TYPE_EMPTY_VALUE = ""

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

DISPATCH_ADD = "add_device"
DISPATCH_ADOPT = "adopt_device"
DISPATCH_CHANNELS = "new_camera_channels"
