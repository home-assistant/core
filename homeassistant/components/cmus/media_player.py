"""Support for interacting with and controlling the cmus music player."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC, MEDIA_TYPE_PLAYLIST, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'cmus'
DEFAULT_PORT = 3000

SUPPORT_CMUS = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_TURN_OFF |  \
    SUPPORT_TURN_ON | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_SEEK | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_HOST, 'remote'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'remote'): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up the CMUS platform."""
    from pycmus import exceptions

    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)

    try:
        cmus_remote = CmusDevice(host, password, port, name)
    except exceptions.InvalidPassword:
        _LOGGER.error("The provided password was rejected by cmus")
        return False
    add_entities([cmus_remote], True)


class CmusDevice(MediaPlayerDevice):
    """Representation of a running cmus."""

    # pylint: disable=no-member
    def __init__(self, server, password, port, name):
        """Initialize the CMUS device."""
        from pycmus import remote

        if server:
            self.cmus = remote.PyCmus(
                server=server, password=password, port=port)
            auto_name = 'cmus-{}'.format(server)
        else:
            self.cmus = remote.PyCmus()
            auto_name = 'cmus-local'
        self._name = name or auto_name
        self.status = {}

    def update(self):
        """Get the latest data and update the state."""
        status = self.cmus.get_status_dict()
        if not status:
            _LOGGER.warning("Received no status from cmus")
        else:
            self.status = status

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the media state."""
        if self.status.get('status') == 'playing':
            return STATE_PLAYING
        if self.status.get('status') == 'paused':
            return STATE_PAUSED
        return STATE_OFF

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self.status.get('file')

    @property
    def content_type(self):
        """Content type of the current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self.status.get('duration')

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.status['tag'].get('title')

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self.status['tag'].get('artist')

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return self.status['tag'].get('tracknumber')

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self.status['tag'].get('album')

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        return self.status['tag'].get('albumartist')

    @property
    def volume_level(self):
        """Return the volume level."""
        left = self.status['set'].get('vol_left')[0]
        right = self.status['set'].get('vol_right')[0]
        if left != right:
            volume = float(left + right) / 2
        else:
            volume = left
        return int(volume)/100

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_CMUS

    def turn_off(self):
        """Service to send the CMUS the command to stop playing."""
        self.cmus.player_stop()

    def turn_on(self):
        """Service to send the CMUS the command to start playing."""
        self.cmus.player_play()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.cmus.set_volume(int(volume * 100))

    def volume_up(self):
        """Set the volume up."""
        left = self.status['set'].get('vol_left')
        right = self.status['set'].get('vol_right')
        if left != right:
            current_volume = float(left + right) / 2
        else:
            current_volume = left

        if current_volume <= 100:
            self.cmus.set_volume(int(current_volume) + 5)

    def volume_down(self):
        """Set the volume down."""
        left = self.status['set'].get('vol_left')
        right = self.status['set'].get('vol_right')
        if left != right:
            current_volume = float(left + right) / 2
        else:
            current_volume = left

        if current_volume <= 100:
            self.cmus.set_volume(int(current_volume) - 5)

    def play_media(self, media_type, media_id, **kwargs):
        """Send the play command."""
        if media_type in [MEDIA_TYPE_MUSIC, MEDIA_TYPE_PLAYLIST]:
            self.cmus.player_play_file(media_id)
        else:
            _LOGGER.error(
                "Invalid media type %s. Only %s and %s are supported",
                media_type, MEDIA_TYPE_MUSIC, MEDIA_TYPE_PLAYLIST)

    def media_pause(self):
        """Send the pause command."""
        self.cmus.player_pause()

    def media_next_track(self):
        """Send next track command."""
        self.cmus.player_next()

    def media_previous_track(self):
        """Send next track command."""
        self.cmus.player_prev()

    def media_seek(self, position):
        """Send seek command."""
        self.cmus.seek(position)

    def media_play(self):
        """Send the play command."""
        self.cmus.player_play()

    def media_stop(self):
        """Send the stop command."""
        self.cmus.stop()
