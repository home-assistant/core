"""
Volumio Platform.

Volumio rest API: https://volumio.github.io/docs/API/REST_API.html
"""
from datetime import timedelta
import json

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.util import Throttle

from .browse_media import browse_node, browse_top_level
from .const import DATA_INFO, DATA_VOLUMIO, DOMAIN

_CONFIGURING = {}

SUPPORT_VOLUMIO = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_BROWSE_MEDIA
)

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Volumio media player platform."""

    data = hass.data[DOMAIN][config_entry.entry_id]
    volumio = data[DATA_VOLUMIO]
    info = data[DATA_INFO]
    uid = config_entry.data[CONF_ID]
    name = config_entry.data[CONF_NAME]

    entity = Volumio(volumio, uid, name, info)
    async_add_entities([entity])


class Volumio(MediaPlayerEntity):
    """Volumio Player Object."""

    def __init__(self, volumio, uid, name, info):
        """Initialize the media player."""
        self._volumio = volumio
        self._uid = uid
        self._name = name
        self._info = info
        self._state = {}
        self._playlists = []
        self._currentplaylist = None

    async def async_update(self):
        """Update state."""
        self._state = await self._volumio.get_state()
        await self._async_update_playlists()

    @property
    def unique_id(self):
        """Return the unique id for the entity."""
        return self._uid

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Volumio",
            "sw_version": self._info["systemversion"],
            "model": self._info["hardware"],
        }

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def state(self):
        """Return the state of the device."""
        status = self._state.get("status", None)
        if status == "pause":
            return STATE_PAUSED
        if status == "play":
            return STATE_PLAYING

        return STATE_IDLE

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._state.get("title", None)

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._state.get("artist", None)

    @property
    def media_album_name(self):
        """Artist of current playing media (Music track only)."""
        return self._state.get("album", None)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        url = self._state.get("albumart", None)
        return self._volumio.canonic_url(url)

    @property
    def media_seek_position(self):
        """Time in seconds of current seek position."""
        return self._state.get("seek", None)

    @property
    def media_duration(self):
        """Time in seconds of current song duration."""
        return self._state.get("duration", None)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume = self._state.get("volume", None)
        if volume is not None and volume != "":
            volume = int(volume) / 100
        return volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._state.get("mute", None)

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._state.get("random", False)

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._playlists

    @property
    def source(self):
        """Name of the current input source."""
        return self._currentplaylist

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_VOLUMIO

    async def async_media_next_track(self):
        """Send media_next command to media player."""
        await self._volumio.next()

    async def async_media_previous_track(self):
        """Send media_previous command to media player."""
        await self._volumio.previous()

    async def async_media_play(self):
        """Send media_play command to media player."""
        await self._volumio.play()

    async def async_media_pause(self):
        """Send media_pause command to media player."""
        if self._state["trackType"] == "webradio":
            await self._volumio.stop()
        else:
            await self._volumio.pause()

    async def async_media_stop(self):
        """Send media_stop command to media player."""
        await self._volumio.stop()

    async def async_set_volume_level(self, volume):
        """Send volume_up command to media player."""
        await self._volumio.set_volume_level(int(volume * 100))

    async def async_volume_up(self):
        """Service to send the Volumio the command for volume up."""
        await self._volumio.volume_up()

    async def async_volume_down(self):
        """Service to send the Volumio the command for volume down."""
        await self._volumio.volume_down()

    async def async_mute_volume(self, mute):
        """Send mute command to media player."""
        if mute:
            await self._volumio.mute()
        else:
            await self._volumio.unmute()

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self._volumio.set_shuffle(shuffle)

    async def async_select_source(self, source):
        """Choose an available playlist and play it."""
        await self._volumio.play_playlist(source)
        self._currentplaylist = source

    async def async_clear_playlist(self):
        """Clear players playlist."""
        await self._volumio.clear_playlist()
        self._currentplaylist = None

    @Throttle(PLAYLIST_UPDATE_INTERVAL)
    async def _async_update_playlists(self, **kwargs):
        """Update available Volumio playlists."""
        self._playlists = await self._volumio.get_playlists()

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        await self._volumio.replace_and_play(json.loads(media_id))

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        if media_content_type in [None, "library"]:
            return await browse_top_level(self._volumio)

        return await browse_node(self._volumio, media_content_type, media_content_id)
