"""Constant definitions for UniFi Protect Integration."""

from pyunifiprotect.data.types import ModelType, Version
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.helpers import config_validation as cv

DOMAIN = "unifiprotect"

ATTR_EVENT_SCORE = "event_score"
ATTR_EVENT_THUMB = "event_thumbnail"
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

TYPE_EMPTY_VALUE = ""

SERVICE_ADD_DOORBELL_TEXT = "add_doorbell_text"
SERVICE_REMOVE_DOORBELL_TEXT = "remove_doorbell_text"
SERVICE_SET_DEFAULT_DOORBELL_TEXT = "set_default_doorbell_text"

ALL_GLOBAL_SERIVCES = [
    SERVICE_ADD_DOORBELL_TEXT,
    SERVICE_REMOVE_DOORBELL_TEXT,
    SERVICE_SET_DEFAULT_DOORBELL_TEXT,
]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


DOORBELL_TEXT_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
            vol.Required(ATTR_MESSAGE): cv.string,
        },
    ),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)

GENERATE_DATA_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
            vol.Required(ATTR_DURATION): vol.Coerce(int),
            vol.Required(ATTR_ANONYMIZE): vol.Coerce(bool),
        },
    ),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)

PROFILE_WS_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
            vol.Required(ATTR_DURATION): vol.Coerce(int),
        },
    ),
    cv.has_at_least_one_key(ATTR_DEVICE_ID),
)

SET_DOORBELL_LCD_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DURATION, default="None"): cv.string,
    }
)
