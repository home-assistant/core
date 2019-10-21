"""Platform for Sky+HD integration."""
import logging

import PySkyPlusHD
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDevice, PLATFORM_SCHEMA
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Sky+HD"
ICON = "mdi:set-top-box"

SERVICE_RECORD = ""

SUPPORT_SKYPLUSHD = (
    SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sky+HD platform."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    sky = PySkyPlusHD.SkyBox(host)

    add_entities([SkyPlusHD(sky, name)])


class SkyPlusHD(MediaPlayerDevice):
    """Representation of a Sky+HD box."""

    def __init__(self, sky, name):
        """Initialize the Sky+HD box."""
        self._sky = sky
        self._name = name
        self._state = None

    def update(self):
        """Get the latest details from the device."""
        self._state = STATE_ON if self._sky.getState() else STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the device."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SKYPLUSHD

    def turn_off(self):
        """Turn off the media player."""
        self._sky.sendButton("power")

    def turn_on(self):
        """Turn on the media player."""
        self._sky.sendButton("power")

    def media_pause(self):
        """Send pause command."""
        self._sky.sendButton("pause")

    def media_play_pause(self):
        """Simulate play pause media player."""
        self._sky.sendButton("pause")

    def media_play(self):
        """Send play command."""
        self._sky.sendButton("play")

    def media_stop(self):
        """Send stop command."""
        self._sky.sendButton("stop")

    def media_next(self):
        """Send next track command."""
        self._sky.sendButton("fastforward")

    def media_previous(self):
        """Send previous track command."""
        self._sky.sendButton("rewind")
