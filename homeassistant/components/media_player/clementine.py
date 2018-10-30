"""
Support for Clementine Music Player as media player.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.clementine/
"""
from datetime import timedelta
import logging
import time

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF,
    STATE_PAUSED, STATE_PLAYING)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-clementine-remote==1.0.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Clementine Remote'
DEFAULT_PORT = 5500

SCAN_INTERVAL = timedelta(seconds=5)

SUPPORT_CLEMENTINE = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
                     SUPPORT_PREVIOUS_TRACK | SUPPORT_VOLUME_SET | \
                     SUPPORT_NEXT_TRACK | \
                     SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ACCESS_TOKEN): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Clementine platform."""
    from clementineremote import ClementineRemote
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    token = config.get(CONF_ACCESS_TOKEN)

    client = ClementineRemote(host, port, token, reconnect=True)

    add_entities([ClementineDevice(client, config[CONF_NAME])])


class ClementineDevice(MediaPlayerDevice):
    """Representation of Clementine Player."""

    def __init__(self, client, name):
        """Initialize the Clementine device."""
        self._client = client
        self._name = name
        self._muted = False
        self._volume = 0.0
        self._track_id = 0
        self._last_track_id = 0
        self._track_name = ''
        self._track_artist = ''
        self._track_album_name = ''
        self._state = None

    def update(self):
        """Retrieve the latest data from the Clementine Player."""
        try:
            client = self._client

            if client.state == 'Playing':
                self._state = STATE_PLAYING
            elif client.state == 'Paused':
                self._state = STATE_PAUSED
            elif client.state == 'Disconnected':
                self._state = STATE_OFF
            else:
                self._state = STATE_PAUSED

            if client.last_update and (time.time() - client.last_update > 40):
                self._state = STATE_OFF

            self._volume = float(client.volume) if client.volume else 0.0

            if client.current_track:
                self._track_id = client.current_track['track_id']
                self._track_name = client.current_track['title']
                self._track_artist = client.current_track['track_artist']
                self._track_album_name = client.current_track['track_album']

        except Exception:
            self._state = STATE_OFF
            raise

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
        return self._volume / 100.0

    @property
    def source(self):
        """Return  current source name."""
        source_name = "Unknown"
        client = self._client
        if client.active_playlist_id in client.playlists:
            source_name = client.playlists[client.active_playlist_id]['name']
        return source_name

    @property
    def source_list(self):
        """List of available input sources."""
        source_names = [s["name"] for s in self._client.playlists.values()]
        return source_names

    def select_source(self, source):
        """Select input source."""
        client = self._client
        sources = [s for s in client.playlists.values() if s['name'] == source]
        if len(sources) == 1:
            client.change_song(sources[0]['id'], 0)

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._track_name

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._track_artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._track_album_name

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_CLEMENTINE

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        if self._client.current_track:
            return self._client.current_track['track_id']

        return None

    async def async_get_media_image(self):
        """Fetch media image of current playing image."""
        if self._client.current_track:
            image = bytes(self._client.current_track['art'])
            return (image, 'image/png')

        return None, None

    def volume_up(self):
        """Volume up the media player."""
        newvolume = min(self._client.volume + 4, 100)
        self._client.set_volume(newvolume)

    def volume_down(self):
        """Volume down media player."""
        newvolume = max(self._client.volume - 4, 0)
        self._client.set_volume(newvolume)

    def mute_volume(self, mute):
        """Send mute command."""
        self._client.set_volume(0)

    def set_volume_level(self, volume):
        """Set volume level."""
        self._client.set_volume(int(100 * volume))

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._state == STATE_PLAYING:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._state = STATE_PLAYING
        self._client.play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._state = STATE_PAUSED
        self._client.pause()

    def media_next_track(self):
        """Send next track command."""
        self._client.next()

    def media_previous_track(self):
        """Send the previous track command."""
        self._client.previous()
