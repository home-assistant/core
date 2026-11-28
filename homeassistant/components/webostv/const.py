"""Constants for the LG webOS TV integration."""

from enum import StrEnum
import logging

from homeassistant.const import Platform

DOMAIN = "webostv"
LOGGER = logging.getLogger(__package__)
PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SWITCH]
DEFAULT_NAME = "LG webOS TV"

ATTR_ICON = "icon"
ATTR_SOUND_OUTPUT = "sound_output"

CONF_ON_ACTION = "turn_on_action"
CONF_SOURCES = "sources"
CONF_WAKE_ON_LAN = "wake_on_lan"


class WebOsTvService(StrEnum):
    """Store keys for LG webOS TV services."""

    BUTTON = "button"
    COMMAND = "command"
    SELECT_SOUND_OUTPUT = "select_sound_output"


class WebOsTvServiceArgument(StrEnum):
    """Store keys for LG webOS TV service arguments."""

    BUTTON = "button"
    COMMAND = "command"
    PAYLOAD = "payload"
    SOUND_OUTPUT = "sound_output"


LIVE_TV_APP_ID = "com.webos.app.livetv"
