"""Constants for the Dynalite component."""

import logging

from homeassistant.const import CONF_ROOM, Platform

LOGGER = logging.getLogger(__package__)
DOMAIN = "dynalite"

PLATFORMS = [Platform.COVER, Platform.LIGHT, Platform.SWITCH]


CONF_ACTIVE = "active"
ACTIVE_INIT = "init"
ACTIVE_OFF = "off"
ACTIVE_ON = "on"
CONF_AREA = "area"
CONF_AUTO_DISCOVER = "autodiscover"
CONF_BRIDGES = "bridges"
CONF_CHANNEL = "channel"
CONF_CHANNEL_COVER = "channel_cover"
CONF_CLOSE_PRESET = "close"
CONF_DEVICE_CLASS = "class"
CONF_DURATION = "duration"
CONF_FADE = "fade"
CONF_LEVEL = "level"
CONF_NO_DEFAULT = "nodefault"
CONF_OPEN_PRESET = "open"
CONF_POLL_TIMER = "polltimer"
CONF_PRESET = "preset"
CONF_ROOM_OFF = "room_off"
CONF_ROOM_ON = "room_on"
CONF_STOP_PRESET = "stop"
CONF_TEMPLATE = "template"
CONF_TILT_TIME = "tilt"
CONF_TIME_COVER = "time_cover"

DEFAULT_CHANNEL_TYPE = "light"
DEFAULT_NAME = "dynalite"
DEFAULT_PORT = 12345
DEFAULT_TEMPLATES = {
    CONF_ROOM: [CONF_ROOM_ON, CONF_ROOM_OFF],
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

ATTR_AREA = "area"
ATTR_CHANNEL = "channel"
ATTR_HOST = "host"
ATTR_PACKET = "packet"
ATTR_PRESET = "preset"

SERVICE_REQUEST_AREA_PRESET = "request_area_preset"
SERVICE_REQUEST_CHANNEL_LEVEL = "request_channel_level"
