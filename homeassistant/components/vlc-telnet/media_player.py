"""Provide functionality to interact with the vlc telnet interface over the
network."""
import logging
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC, SUPPORT_PAUSE, SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA, SUPPORT_STOP, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_NEXT_TRACK, SUPPORT_CLEAR_PLAYLIST, SUPPORT_SHUFFLE_SET)
from homeassistant.const import (
    CONF_NAME, STATE_IDLE, STATE_PAUSED, STATE_PLAYING, STATE_UNAVAILABLE)
import homeassistant.helpers.config_validation as cv

import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vlc_telnet'

DEFAULT_NAME = 'Vlc Telnet'
TELNET_HOST = 'telnet_host'
TELNET_PORT = 'telnet_port'

SUPPORT_VLC = SUPPORT_PAUSE | SUPPORT_SEEK | SUPPORT_VOLUME_SET \
              | SUPPORT_VOLUME_MUTE | SUPPORT_PREVIOUS_TRACK \
              | SUPPORT_NEXT_TRACK | SUPPORT_PLAY_MEDIA | SUPPORT_STOP \
              | SUPPORT_CLEAR_PLAYLIST | SUPPORT_PLAY \
              | SUPPORT_SHUFFLE_SET
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(TELNET_HOST, default='127.0.0.1'): cv.string,
    vol.Optional(TELNET_PORT, default='4212'): cv.string,
    vol.Optional(CONF_NAME, default='VLC-TELNET'): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the vlc platform."""
    add_entities([VlcDevice(config.get(CONF_NAME),
                            config.get(TELNET_HOST),
                            config.get(TELNET_PORT))])


def setup(hass, config):
    hass.states.set('hello_state.world', 'Paulus')

    # Return boolean to indicate that initialization was successful.
    return True


class VlcDevice(MediaPlayerDevice):
    def __init__(self, name, host, port):
        """Initialize the vlc device."""
        self._instance = None
        self._name = name
        self._volume = None
        self._muted = None
        self._state = None
        self._media_position_updated_at = None
        self._media_position = None
        self._media_duration = None
        self._host = host
        self._port = port
        self._vlc = None
        print("loaded!")

    def update(self):
        """Get the latest details from the device."""
        from python_telnet_vlc import VLCTelnet

        if self._vlc is None:
            try:
                self._vlc = VLCTelnet(self._host,
                                      "test", self._port)
                self._state = STATE_IDLE
            except ConnectionError:
                self._state = STATE_UNAVAILABLE
        else:
            status = self._vlc.status()
            if status:
                if 'volume' in status:
                    self._volume = status['volume']
                if 'state' in status:
                    state = status["state"]
                    if state == "playing":
                        self._state = STATE_PLAYING
                    elif state == "paused":
                        self._state = STATE_PAUSED
                    else:
                        self._state = STATE_IDLE
                else:
                    self._state = STATE_IDLE

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
        track_length = self._vlc.get_length() / 1000
        self._vlc.seek(position)

    def mute_volume(self, mute):
        """Mute the volume."""
        self._vlc.set_volume(0)
        self._muted = mute

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._vlc.set_volume(int(volume * 100))
        self._volume = volume

    def media_play(self):
        """Send play command."""
        self._vlc.play()
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self._vlc.pause()
        self._state = STATE_PAUSED

    def media_stop(self):
        """Send stop command."""
        self._vlc.stop()
        self._state = STATE_IDLE

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL or file."""
        if not media_type == MEDIA_TYPE_MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type, MEDIA_TYPE_MUSIC)
            return
        self._vlc.add(media_id)
        self._vlc.play()
        self._state = STATE_PLAYING

    def turn_on(self):
        pass

    def turn_off(self):
        pass

    def media_previous_track(self):
        self._vlc.prev()

    def media_next_track(self):
        self._vlc.next()

    def select_source(self, source):
        pass

    def select_sound_mode(self, sound_mode):
        pass

    def clear_playlist(self):
        pass

    def set_shuffle(self, shuffle):
        self._vlc.random(shuffle)
