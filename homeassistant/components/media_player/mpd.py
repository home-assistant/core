"""
Support to interact with a Music Player Daemon.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.mpd/
"""
import logging
import socket
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, PLATFORM_SCHEMA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP,
    SUPPORT_VOLUME_SET, SUPPORT_PLAY_MEDIA, SUPPORT_PLAY, MEDIA_TYPE_PLAYLIST,
    SUPPORT_SELECT_SOURCE, SUPPORT_CLEAR_PLAYLIST, SUPPORT_SHUFFLE_SET,
    SUPPORT_SEEK, MediaPlayerDevice)
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_PAUSED, STATE_PLAYING,
    CONF_PORT, CONF_PASSWORD, CONF_HOST, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['python-mpd2==0.5.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MPD'
DEFAULT_PORT = 6600

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SUPPORT_MPD = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_PLAY | SUPPORT_SELECT_SOURCE | \
    SUPPORT_CLEAR_PLAYLIST | SUPPORT_SHUFFLE_SET | SUPPORT_SEEK | \
    SUPPORT_STOP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MPD platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)

    device = MpdDevice(host, port, password, name)
    add_devices([device])


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

        self.status = None
        self.currentsong = None
        self.playlists = []
        self.currentplaylist = None
        self._is_connected = False

        # set up MPD client
        self.client = mpd.MPDClient()
        self.client.timeout = 5
        self.client.idletimeout = None
        if password is not None:
            self.client.password(password)

    def _connect(self):
        """Connect to MPD."""
        import mpd
        try:
            self.client.connect(self.server, self.port)
        except mpd.ConnectionError:
            return

        self._is_connected = True

    def _disconnect(self):
        """Disconnect from MPD."""
        import mpd
        try:
            self.client.disconnect()
        except mpd.ConnectionError:
            pass
        self._is_connected = False
        self._state = None

    def _fetch_status(self):
        """Fetch status from MPD."""
        self.status = self.client.status()
        self.currentsong = self.client.currentsong()

        self._update_playlists()

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
        if not self.status:
            return STATE_OFF
        elif self.status['state'] == 'play':
            return STATE_PLAYING
        elif self.status['state'] == 'pause':
            return STATE_PAUSED

        return STATE_ON

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self.currentsong.get('file')

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        # Time does not exist for streams
        return self.currentsong.get('time')

    @property
    def media_title(self):
        """Return the title of current playing media."""
        name = self.currentsong.get('name', None)
        title = self.currentsong.get('title', None)

        if name is None and title is None:
            return "None"
        elif name is None:
            return title
        elif title is None:
            return name

        return '{}: {}'.format(name, title)

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        return self.currentsong.get('artist')

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return self.currentsong.get('album')

    @property
    def volume_level(self):
        """Return the volume level."""
        return int(self.status['volume'])/100

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_MPD

    @property
    def source(self):
        """Name of the current input source."""
        return self.currentplaylist

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self.playlists

    def select_source(self, source):
        """Choose a different available playlist and play it."""
        self.play_media(MEDIA_TYPE_PLAYLIST, source)

    @Throttle(PLAYLIST_UPDATE_INTERVAL)
    def _update_playlists(self, **kwargs):
        """Update available MPD playlists."""
        self.playlists = []
        for playlist_data in self.client.listplaylists():
            self.playlists.append(playlist_data['playlist'])

    def set_volume_level(self, volume):
        """Set volume of media player."""
        self.client.setvol(int(volume * 100))

    def volume_up(self):
        """Service to send the MPD the command for volume up."""
        current_volume = int(self.status['volume'])

        if current_volume <= 100:
            self.client.setvol(current_volume + 5)

    def volume_down(self):
        """Service to send the MPD the command for volume down."""
        current_volume = int(self.status['volume'])

        if current_volume >= 0:
            self.client.setvol(current_volume - 5)

    def media_play(self):
        """Service to send the MPD the command for play/pause."""
        self.client.pause(0)

    def media_pause(self):
        """Service to send the MPD the command for play/pause."""
        self.client.pause(1)

    def media_stop(self):
        """Service to send the MPD the command for stop."""
        self.client.stop()

    def media_next_track(self):
        """Service to send the MPD the command for next track."""
        self.client.next()

    def media_previous_track(self):
        """Service to send the MPD the command for previous track."""
        self.client.previous()

    def play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a playlist."""
        _LOGGER.debug(str.format("Playing playlist: {0}", media_id))
        if media_type == MEDIA_TYPE_PLAYLIST:
            if media_id in self.playlists:
                self.currentplaylist = media_id
            else:
                self.currentplaylist = None
                _LOGGER.warning(str.format("Unknown playlist name %s.",
                                           media_id))
            self.client.clear()
            self.client.load(media_id)
            self.client.play()
        else:
            self.client.clear()
            self.client.add(media_id)
            self.client.play()

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return bool(self.status['random'])

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self.client.random(int(shuffle))

    def clear_playlist(self):
        """Clear players playlist."""
        self.client.clear()

    def media_seek(self, position):
        """Send seek command."""
        self.client.seekcur(position)
