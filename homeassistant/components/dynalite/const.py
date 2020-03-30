"""Constants for the Dynalite component."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "dynalite"

ENTITY_PLATFORMS = ["light", "switch", "cover"]


CONF_ACTIVE = "active"
CONF_ACTIVE_INIT = "init"
CONF_ACTIVE_OFF = "off"
CONF_ACTIVE_ON = "on"
CONF_ALL = "ALL"
CONF_AREA = "area"
CONF_AUTO_DISCOVER = "autodiscover"
CONF_BRIDGES = "bridges"
CONF_CHANNEL = "channel"
CONF_CHANNEL_COVER = "channelcover"
CONF_CHANNEL_TYPE = "type"
CONF_CLOSE_PRESET = "close"
CONF_DEFAULT = "default"
CONF_DEVICE_CLASS = "class"
CONF_DURATION = "duration"
CONF_FADE = "fade"
CONF_HOST = "host"
CONF_NAME = "name"
CONF_NO_DEFAULT = "nodefault"
CONF_OPEN_PRESET = "open"
CONF_POLL_TIMER = "polltimer"
CONF_PORT = "port"
CONF_PRESET = "preset"
CONF_ROOM = "room"
CONF_ROOM_OFF = "room_off"
CONF_ROOM_ON = "room_on"
CONF_STOP_PRESET = "stop"
CONF_TEMPLATE = "template"
CONF_TILT_TIME = "tilt"
CONF_TIME_COVER = "timecover"
CONF_TRIGGER = "trigger"

DEFAULT_CHANNEL_TYPE = "light"
DEFAULT_COVER_CLASS = "shutter"
DEFAULT_NAME = "dynalite"
DEFAULT_PORT = 12345
DEFAULT_TEMPLATES = {
    CONF_ROOM: [CONF_ROOM_ON, CONF_ROOM_OFF],
    CONF_TRIGGER: [CONF_TRIGGER],
    CONF_TIME_COVER: [
        CONF_CHANNEL_COVER,
        CONF_DEVICE_CLASS,
        CONF_OPEN_PRESET,
        CONF_CLOSE_PRESET,
        CONF_STOP_PRESET,
        CONF_DURATION,
        CONF_TILT_TIME,
    ],
}
