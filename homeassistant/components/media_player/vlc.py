"""
Provide functionality to interact with vlc devices on the network.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.vlc/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_PLAY, MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_MUSIC)
from homeassistant.const import (CONF_NAME, STATE_IDLE, STATE_PAUSED,
                                 STATE_PLAYING)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['python-vlc==1.1.2']

_LOGGER = logging.getLogger(__name__)

CONF_ARGUMENTS = 'arguments'
DEFAULT_NAME = 'Vlc'

SUPPORT_VLC = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PLAY_MEDIA | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ARGUMENTS, default=''): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the vlc platform."""
    add_devices([VlcDevice(config.get(CONF_NAME, DEFAULT_NAME),
                           config.get(CONF_ARGUMENTS))])


class VlcDevice(MediaPlayerDevice):
    """Representation of a vlc player."""

    def __init__(self, name, arguments):
        """Initialize the vlc device."""
        import vlc
        self._instance = vlc.Instance(arguments)
        self._vlc = self._instance.media_player_new()
        self._name = name
        self._volume = None
        self._muted = None
        self._state = None
        self._media_position_updated_at = None
        self._media_position = None
        self._media_duration = None

    def update(self):
        """Get the latest details from the device."""
        import vlc
        status = self._vlc.get_state()
        if status == vlc.State.Playing:
            self._state = STATE_PLAYING
        elif status == vlc.State.Paused:
            self._state = STATE_PAUSED
        else:
            self._state = STATE_IDLE
        self._media_duration = self._vlc.get_length()/1000
        position = self._vlc.get_position() * self._media_duration
        if position != self._media_position:
            self._media_position_updated_at = dt_util.utcnow()
            self._media_position = position

        self._volume = self._vlc.audio_get_volume() / 100
        self._muted = (self._vlc.audio_get_mute() == 1)

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

    def media_seek(self, position):
        """Seek the media to a specific location."""
        track_length = self._vlc.get_length()/1000
        self._vlc.set_position(position/track_length)

    def mute_volume(self, mute):
        """Mute the volume."""
        self._vlc.audio_set_mute(mute)
        self._muted = mute

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._vlc.audio_set_volume(int(volume * 100))
        self._volume = volume

    def media_play(self):
        """Send play commmand."""
        self._vlc.play()
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self._vlc.pause()
        self._state = STATE_PAUSED

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL or file."""
        if not media_type == MEDIA_TYPE_MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type, MEDIA_TYPE_MUSIC)
            return
        self._vlc.set_media(self._instance.media_new(media_id))
        self._vlc.play()
        self._state = STATE_PLAYING
