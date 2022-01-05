"""Constant definitions for UniFi Protect Integration."""

from datetime import timedelta

from pyunifiprotect.data.types import ModelType, Version
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.helpers import config_validation as cv

DOMAIN = "unifiprotect"

ATTR_WIDTH = "width"
ATTR_HEIGHT = "height"
ATTR_FPS = "fps"
ATTR_BITRATE = "bitrate"
ATTR_CHANNEL_ID = "channel_id"
ATTR_MESSAGE = "message"
ATTR_DURATION = "duration"

CONF_DISABLE_RTSP = "disable_rtsp"
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
DEFAULT_SCAN_INTERVAL = 5
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
OUTDATED_LOG_MESSAGE = "You are running v%s of UniFi Protect. Minimum required version is v%s. Please upgrade UniFi Protect and then retry"

SERVICE_SET_DOORBELL_MESSAGE = "set_doorbell_message"

TYPE_EMPTY_VALUE = ""

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

SET_DOORBELL_LCD_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DURATION, default=""): cv.string,
    }
)
