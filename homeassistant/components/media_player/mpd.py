"""
Support to interact with a Music Player Daemon.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.mpd/
"""
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC, MEDIA_TYPE_PLAYLIST,
    SUPPORT_CLEAR_PLAYLIST, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE, SUPPORT_SHUFFLE_SET, SUPPORT_STOP, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['python-mpd2==1.0.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MPD'
DEFAULT_PORT = 6600

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SUPPORT_MPD = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_PLAY_MEDIA | SUPPORT_PLAY | \
    SUPPORT_CLEAR_PLAYLIST | SUPPORT_SHUFFLE_SET | SUPPORT_SEEK | \
    SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MPD platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)

    device = MpdDevice(host, port, password, name)
    add_entities([device], True)


class MpdDevice(MediaPlayerDevice):
    """Representation of a MPD server."""

    # pylint: disable=no-member
    def __init__(self, server, port, password, name):
        """Initialize the MPD device."""
        import mpd

        self.server = server
        self.port = port
        self._name = name
        self.password = password

        self._status = None
        self._currentsong = None
        self._playlists = None
        self._currentplaylist = None
        self._is_connected = False
        self._muted = False
        self._muted_volume = 0

        # set up MPD client
        self._client = mpd.MPDClient()
        self._client.timeout = 30
        self._client.idletimeout = None

    def _connect(self):
        """Connect to MPD."""
        import mpd
        try:
            self._client.connect(self.server, self.port)

            if self.password is not None:
                self._client.password(self.password)
        except mpd.ConnectionError:
            return

        self._is_connected = True

    def _disconnect(self):
        """Disconnect from MPD."""
        import mpd
        try:
            self._client.disconnect()
        except mpd.ConnectionError:
            pass
        self._is_connected = False
        self._status = None

    def _fetch_status(self):
        """Fetch status from MPD."""
        self._status = self._client.status()
        self._currentsong = self._client.currentsong()

        self._update_playlists()

    @property
    def available(self):
        """Return true if MPD is available and connected."""
        return self._is_connected

    def update(self):
        """Get the latest data and update the state."""
        import mpd

        try:
            if not self._is_connected:
                self._connect()

            self._fetch_status()
        except (mpd.ConnectionError, OSError, BrokenPipeError, ValueError):
            # Cleanly disconnect in case connection is not in valid state
            self._disconnect()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the media state."""
        if self._status is None:
            return STATE_OFF
        if self._status['state'] == 'play':
            return STATE_PLAYING
        if self._status['state'] == 'pause':
            return STATE_PAUSED
        if self._status['state'] == 'stop':
            return STATE_OFF

        return STATE_OFF

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._currentsong.get('file')

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        # Time does not exist for streams
        return self._currentsong.get('time')

    @property
    def media_title(self):
        """Return the title of current playing media."""
        name = self._currentsong.get('name', None)
        title = self._currentsong.get('title', None)
        file_name = self._currentsong.get('file', None)

        if name is None and title is None:
            if file_name is None:
                return "None"
            return os.path.basename(file_name)
        if name is None:
            return title
        if title is None:
            return name

        return '{}: {}'.format(name, title)

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        return self._currentsong.get('artist')

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return self._currentsong.get('album')

    @property
    def volume_level(self):
        """Return the volume level."""
        if 'volume' in self._status:
            return int(self._status['volume'])/100
        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._status is None:
            return None

        supported = SUPPORT_MPD
        if 'volume' in self._status:
            supported |= \
                SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE
        if self._playlists is not None:
            supported |= SUPPORT_SELECT_SOURCE

        return supported

    @property
    def source(self):
        """Name of the current input source."""
        return self._currentplaylist

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._playlists

    def select_source(self, source):
        """Choose a different available playlist and play it."""
        self.play_media(MEDIA_TYPE_PLAYLIST, source)

    @Throttle(PLAYLIST_UPDATE_INTERVAL)
    def _update_playlists(self, **kwargs):
        """Update available MPD playlists."""
        import mpd

        try:
            self._playlists = []
            for playlist_data in self._client.listplaylists():
                self._playlists.append(playlist_data['playlist'])
        except mpd.CommandError as error:
            self._playlists = None
            _LOGGER.warning("Playlists could not be updated: %s:", error)

    def set_volume_level(self, volume):
        """Set volume of media player."""
        if 'volume' in self._status:
            self._client.setvol(int(volume * 100))

    def volume_up(self):
        """Service to send the MPD the command for volume up."""
        if 'volume' in self._status:
            current_volume = int(self._status['volume'])

            if current_volume <= 100:
                self._client.setvol(current_volume + 5)

    def volume_down(self):
        """Service to send the MPD the command for volume down."""
        if 'volume' in self._status:
            current_volume = int(self._status['volume'])

            if current_volume >= 0:
                self._client.setvol(current_volume - 5)

    def media_play(self):
        """Service to send the MPD the command for play/pause."""
        self._client.pause(0)

    def media_pause(self):
        """Service to send the MPD the command for play/pause."""
        self._client.pause(1)

    def media_stop(self):
        """Service to send the MPD the command for stop."""
        self._client.stop()

    def media_next_track(self):
        """Service to send the MPD the command for next track."""
        self._client.next()

    def media_previous_track(self):
        """Service to send the MPD the command for previous track."""
        self._client.previous()

    def mute_volume(self, mute):
        """Mute. Emulated with set_volume_level."""
        if 'volume' in self._status:
            if mute:
                self._muted_volume = self.volume_level
                self.set_volume_level(0)
            else:
                self.set_volume_level(self._muted_volume)
            self._muted = mute

    def play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a playlist."""
        _LOGGER.debug("Playing playlist: %s", media_id)
        if media_type == MEDIA_TYPE_PLAYLIST:
            if media_id in self._playlists:
                self._currentplaylist = media_id
            else:
                self._currentplaylist = None
                _LOGGER.warning("Unknown playlist name %s", media_id)
            self._client.clear()
            self._client.load(media_id)
            self._client.play()
        else:
            self._client.clear()
            self._client.add(media_id)
            self._client.play()

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return bool(int(self._status['random']))

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._client.random(int(shuffle))

    def turn_off(self):
        """Service to send the MPD the command to stop playing."""
        self._client.stop()

    def turn_on(self):
        """Service to send the MPD the command to start playing."""
        self._client.play()
        self._update_playlists(no_throttle=True)

    def clear_playlist(self):
        """Clear players playlist."""
        self._client.clear()

    def media_seek(self, position):
        """Send seek command."""
        self._client.seekcur(position)
