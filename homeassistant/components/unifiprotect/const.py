"""Constant definitions for UniFi Protect Integration."""

# from typing_extensions import Required
from datetime import timedelta

from pyunifiprotect.data.types import ModelType, Version

DOMAIN = "unifiprotect"

ATTR_EVENT_SCORE = "event_score"
ATTR_EVENT_OBJECT = "event_object"
ATTR_EVENT_THUMB = "event_thumbnail"
ATTR_WIDTH = "width"
ATTR_HEIGHT = "height"
ATTR_FPS = "fps"
ATTR_BITRATE = "bitrate"
ATTR_CHANNEL_ID = "channel_id"

CONF_DOORBELL_TEXT = "doorbell_text"
CONF_DISABLE_RTSP = "disable_rtsp"
CONF_MESSAGE = "message"
CONF_DURATION = "duration"
CONF_ALL_UPDATES = "all_updates"
CONF_OVERRIDE_CHOST = "override_connection_host"

CONFIG_OPTIONS = [
    CONF_ALL_UPDATES,
    CONF_DISABLE_RTSP,
    CONF_OVERRIDE_CHOST,
]

DEFAULT_PORT = 443
DEFAULT_ATTRIBUTION = "Powered by UniFi Protect Server"
DEFAULT_BRAND = "Ubiquiti"
DEFAULT_SCAN_INTERVAL = 2
DEFAULT_VERIFY_SSL = False

RING_INTERVAL = timedelta(seconds=3)

DEVICE_TYPE_CAMERA = "camera"
DEVICES_THAT_ADOPT = {
    ModelType.CAMERA,
    ModelType.LIGHT,
    ModelType.VIEWPORT,
    ModelType.SENSOR,
}
DEVICES_WITH_ENTITIES = DEVICES_THAT_ADOPT | {ModelType.NVR}
DEVICES_FOR_SUBSCRIBE = DEVICES_WITH_ENTITIES | {ModelType.EVENT}

MIN_REQUIRED_PROTECT_V = Version("1.20.0")

PLATFORMS = [
    "camera",
]
