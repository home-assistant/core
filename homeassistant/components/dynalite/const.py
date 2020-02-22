"""Constants for the Dynalite component."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "dynalite"

ENTITY_PLATFORMS = ["light", "switch", "cover"]

CONF_ACTIVE = "active"
CONF_ACTIVE_ON = "on"
CONF_ACTIVE_OFF = "off"
CONF_ACTIVE_INIT = "init"
CONF_ALL = "ALL"
CONF_AREA = "area"
CONF_AUTO_DISCOVER = "autodiscover"
CONF_BRIDGES = "bridges"
CONF_CHANNEL = "channel"
CONF_DEFAULT = "default"
CONF_FADE = "fade"
CONF_HOST = "host"
CONF_NAME = "name"
CONF_POLLTIMER = "polltimer"
CONF_PORT = "port"
CONF_PRESET = "preset"
CONF_TEMPLATE = "template"
CONF_ROOM = "room"
CONF_ROOM_ON = "room_on"
CONF_ROOM_OFF = "room_off"
CONF_TRIGGER = "trigger"
CONF_TIME_COVER = "timecover"
CONF_TILT_TIME = "tilt"
CONF_STOP_PRESET = "stop"
CONF_CHANNEL_CLASS = "class"
CONF_CLOSE_PRESET = "close"
CONF_DURATION = "duration"
CONF_OPEN_PRESET = "open"
CONF_NODEFAULT = "nodefault"
CONF_CHANNEL_COVER = "channelcover"
CONF_CHANNEL_TYPE = "type"

DEFAULT_CHANNEL_TYPE = "light"
DEFAULT_NAME = "dynalite"
DEFAULT_PORT = 12345
DEFAULT_COVER_CHANNEL_CLASS = "shutter"
DEFAULT_TEMPLATES = {
    CONF_ROOM: {CONF_ROOM_ON: "1", CONF_ROOM_OFF: "4"},
    CONF_TRIGGER: {CONF_TRIGGER: "1"},
    CONF_TIME_COVER: {
        CONF_CHANNEL_COVER: "1",
        CONF_CHANNEL_CLASS: DEFAULT_COVER_CHANNEL_CLASS,
        CONF_OPEN_PRESET: "1",
        CONF_CLOSE_PRESET: "2",
        CONF_STOP_PRESET: "4",
        CONF_DURATION: 60,
        CONF_TILT_TIME: 0,
    },
}
