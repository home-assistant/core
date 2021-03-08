"""Provide functionality to interact with vlc devices on the network."""
from functools import wraps
import logging

import vlc
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_ARGUMENTS = "arguments"
DEFAULT_NAME = "Vlc"

SUPPORT_VLC = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ARGUMENTS, default=""): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the vlc platform."""
    add_entities(
        [VlcDevice(config.get(CONF_NAME, DEFAULT_NAME), config.get(CONF_ARGUMENTS))]
    )


def cmd(func):
    """Catch command exceptions when vlc is turned off."""

    @wraps(func)
    def wrapper(obj, *args, **kwargs):
        """Wrap all command methods."""
        try:
            func(obj, *args, **kwargs)
        except AttributeError as exc:
            # If VLC is off, we expect calls to fail.
            if obj.state == STATE_OFF:
                _LOGGER.info(
                    "Cannot call %s on entity %s because it is turned off: %r",
                    func.__name__,
                    obj.entity_id,
                    exc,
                )
            else:
                _LOGGER.error(
                    "Error calling %s on entity %s: %r",
                    func.__name__,
                    obj.entity_id,
                    exc,
                )

    return wrapper


class VlcDevice(MediaPlayerEntity):
    """Representation of a vlc player."""

    def __init__(self, name, arguments):
        """Initialize the vlc device."""
        self._instance = None
        self._vlc = None
        self._name = name
        self._volume = None
        self._muted = None
        self._state = None
        self._media_position_updated_at = None
        self._media_position = None
        self._media_duration = None
        self._arguments = arguments
        self.turn_on()

    @property
    def _vlc_is_off(self):
        """Indicate whether or not the vlc instance is turned off."""
        return self._vlc is None

    def turn_on(self):
        """Create a new instance of the vlc client."""
        self._instance = vlc.Instance(self._arguments)
        self._vlc = self._instance.media_player_new()

    def turn_off(self):
        """Turn off and destroy the current vlc client."""
        self._instance.release()
        self._instance = None
        self._vlc = None

    def update(self):
        """Get the latest details from the device."""
        if self._vlc_is_off:
            self._state = STATE_OFF
            self._media_duration = None
            self._media_position = None
        else:
            status = self._vlc.get_state()
            if status == vlc.State.Playing:
                self._state = STATE_PLAYING
            elif status == vlc.State.Paused:
                self._state = STATE_PAUSED
            else:
                self._state = STATE_IDLE
            self._media_duration = self._vlc.get_length() / 1000
            position = self._vlc.get_position() * self._media_duration
            if position != self._media_position:
                self._media_position_updated_at = dt_util.utcnow()

            self._volume = self._vlc.audio_get_volume() / 100
            self._muted = self._vlc.audio_get_mute() == 1

        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_VLC

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    @cmd
    def media_seek(self, position):
        """Seek the media to a specific location."""
        track_length = self._vlc.get_length() / 1000
        self._vlc.set_position(position / track_length)

    @cmd
    def mute_volume(self, mute):
        """Mute the volume."""
        self._vlc.audio_set_mute(mute)
        self._muted = mute

    @cmd
    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._vlc.audio_set_volume(int(volume * 100))
        self._volume = volume

    @cmd
    def media_play(self):
        """Send play command."""
        self._vlc.play()
        self._state = STATE_PLAYING

    @cmd
    def media_pause(self):
        """Send pause command."""
        self._vlc.pause()
        self._state = STATE_PAUSED

    @cmd
    def media_stop(self):
        """Send stop command."""
        self._vlc.stop()
        self._state = STATE_IDLE

    @cmd
    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL or file."""
        if not media_type == MEDIA_TYPE_MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MEDIA_TYPE_MUSIC,
            )
            return
        self._vlc.set_media(self._instance.media_new(media_id))
        self._vlc.play()
        self._state = STATE_PLAYING
