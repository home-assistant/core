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
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORT_SKYPLUSHD = (
    SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sky+HD platform."""
    host = config[CONF_HOST]

    try:
        sky = PySkyPlusHD.SkyBox(host)
    except RuntimeError:
        _LOGGER.error("Could not connect to the Sky box.")
        raise PlatformNotReady

    add_entities([SkyPlusHD(sky)])


class SkyPlusHD(MediaPlayerDevice):
    """Representation of a Sky+HD box."""

    def __init__(self, sky):
        """Initialize the Sky+HD box."""
        self._sky = sky
        self._state = None

    def update(self):
        """Get the latest details from the device."""
        self._state = STATE_ON if self._sky.getState() else STATE_OFF

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._sky.serial

    @property
    def name(self):
        """Return the name of the device."""
        return f"Sky+HD {self._sky.serial}"

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
