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
    SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET, SUPPORT_PLAY_MEDIA, SUPPORT_PLAY, MEDIA_TYPE_PLAYLIST,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import (
    STATE_OFF, STATE_PAUSED, STATE_PLAYING, CONF_PORT, CONF_PASSWORD,
    CONF_HOST, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['python-mpd2==0.5.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MPD'
DEFAULT_PORT = 6600

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SUPPORT_MPD = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_TURN_OFF | \
    SUPPORT_TURN_ON | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_PLAY | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MPD platform."""
    daemon = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)
    import mpd

    # pylint: disable=no-member
    try:
        mpd_client = mpd.MPDClient()
        mpd_client.connect(daemon, port)

        if password is not None:
            mpd_client.password(password)

        mpd_client.close()
        mpd_client.disconnect()
    except socket.error:
        _LOGGER.error("Unable to connect to MPD")
        return False
    except mpd.CommandError as error:

        if "incorrect password" in str(error):
            _LOGGER.error("MPD reported incorrect password")
            return False
        else:
            raise

    add_devices([MpdDevice(daemon, port, password, name)])


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

        self.client = mpd.MPDClient()
        self.client.timeout = 10
        self.client.idletimeout = None
        self.update()

    def update(self):
        """Get the latest data and update the state."""
        import mpd
        try:
            self.status = self.client.status()
            self.currentsong = self.client.currentsong()
            self._update_playlists()
        except (mpd.ConnectionError, OSError, BrokenPipeError, ValueError):
            # Cleanly disconnect in case connection is not in valid state
            try:
                self.client.disconnect()
            except mpd.ConnectionError:
                pass

            self.client.connect(self.server, self.port)

            if self.password is not None:
                self.client.password(self.password)

            self.status = self.client.status()
            self.currentsong = self.client.currentsong()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the media state."""
        if self.status['state'] == 'play':
            return STATE_PLAYING
        elif self.status['state'] == 'pause':
            return STATE_PAUSED
        else:
            return STATE_OFF

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
        else:
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

    def turn_off(self):
        """Service to send the MPD the command to stop playing."""
        self.client.stop()

    def turn_on(self):
        """Service to send the MPD the command to start playing."""
        self.client.play()
        self._update_playlists(no_throttle=True)

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

    def media_next_track(self):
        """Service to send the MPD the command for next track."""
        self.client.next()

    def media_previous_track(self):
        """Service to send the MPD the command for previous track."""
        self.client.previous()

    def play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a playlist."""
        _LOGGER.info(str.format("Playing playlist: {0}", media_id))
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
