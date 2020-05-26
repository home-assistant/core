"""
Volumio Platform.

Volumio rest API: https://volumio.github.io/docs/API/REST_API.html
"""
import asyncio
from datetime import timedelta
import logging
import socket

import mpd
from volumio_websocket import request as volumio_api_request
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
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
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Volumio"
DEFAULT_PORT = 3000

DATA_VOLUMIO = "volumio"

TIMEOUT = 10

SUPPORT_VOLUMIO = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_CLEAR_PLAYLIST
)

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Volumio platform."""
    if DATA_VOLUMIO not in hass.data:
        hass.data[DATA_VOLUMIO] = {}

    # This is a manual configuration?
    if discovery_info is None:
        name = config.get(CONF_NAME)
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
    else:
        name = "{} ({})".format(DEFAULT_NAME, discovery_info.get("hostname"))
        host = discovery_info.get("host")
        port = discovery_info.get("port")

    # Only add a device once, so discovered devices do not override manual
    # config.
    ip_addr = socket.gethostbyname(host)
    if ip_addr in hass.data[DATA_VOLUMIO]:
        return

    entity = Volumio(name, host, port, hass)

    hass.data[DATA_VOLUMIO][ip_addr] = entity
    async_add_entities([entity])


class Volumio(MediaPlayerEntity):
    """Volumio Player Object."""

    def __init__(self, name, host, port, hass):
        """Initialize the media player."""
        self.host = host
        self.port = port
        self.hass = hass
        self._url = "{}:{}".format(host, str(port))
        self._name = name
        self._state = {}
        self._lastvol = self._state.get("volume", 0)
        self._playlists = []
        self._currentplaylist = None

        self._client = mpd.MPDClient()
        self._client.timeout = 30
        self._client.idletimeout = None

        self._client.connect(self.host, "6600")

    async def send_volumio_msg(self, method, params=None):
        """Handle volumio calls."""
        _LOGGER.debug("Request: method %s, params %s", method, params)
        return await volumio_api_request(self.host, self.port, method, params)

    async def async_update(self):
        """Update state."""
        resp = await self.send_volumio_msg("getState")
        _LOGGER.debug("Got response: %s", resp)
        await self._async_update_playlists()
        if resp is None:
            return
        self._state = resp.copy()

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
        if url is None:
            return
        if str(url[0:2]).lower() == "ht":
            mediaurl = url
        else:
            mediaurl = f"http://{self.host}:{self.port}{url}"
        return mediaurl

    @property
    def media_seek_position(self):
        """Time in seconds of current seek position."""
        self.async_update()
        return self._state.get("seek", None)

    def media_seek(self, position):
        """Send seek command."""
        self.send_volumio_msg("Seek", position)

    def play_media(self, *args, **kwargs):
        """Play a piece of media."""
        self.async_play_media(args, kwargs)

    async def async_mpd_play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a playlist."""
        _LOGGER.debug("Playing playlist: %s", media_id)

        try:
            self._client.status()
        except (mpd.ConnectionError, OSError, BrokenPipeError, ValueError):
            # Cleanly disconnect in case connection is not in valid state
            self._client.connect(self.host, "6600")

        self._client.clear()
        if media_type == MEDIA_TYPE_PLAYLIST:
            if media_id in self._playlists:
                self._currentplaylist = media_id
            else:
                self._currentplaylist = None
                _LOGGER.warning("Unknown playlist name %s", media_id)
            self._client.load(media_id)
        else:
            self._client.add(media_id)

        waittimer = self._client.status().get("duration", 1)
        self._client.play()
        await asyncio.sleep(waittimer)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Async play media."""
        isPlaying = False
        if self.state == STATE_PLAYING:
            isPlaying = True

        if isPlaying:
            await self.send_volumio_msg("pause")
            await asyncio.sleep(
                0.4
            )  # small delay, otherwise pause and play confuse volumio.

        await self.async_mpd_play_media(media_type, media_id, **kwargs)

        wait_seconds = 5
        split_number = 10
        split = wait_seconds / split_number

        counter = 0
        while counter < wait_seconds or self._client.status().get("state") == "play":
            await asyncio.sleep(split)
            counter += split

        self._client.stop()
        if isPlaying:
            await self.send_volumio_msg("play")

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
    def name(self):
        """Return the name of the device."""
        return self._name

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
        await self.send_volumio_msg("commands", params={"cmd": "next"})

    async def async_media_previous_track(self):
        """Send media_previous command to media player."""
        await self.send_volumio_msg("commands", params={"cmd": "prev"})

    async def async_media_play(self):
        """Send media_play command to media player."""
        await self.send_volumio_msg("commands", params={"cmd": "play"})

    async def async_media_pause(self):
        """Send media_pause command to media player."""
        if self._state["trackType"] == "webradio":
            await self.send_volumio_msg("commands", params={"cmd": "stop"})
        else:
            await self.send_volumio_msg("commands", params={"cmd": "pause"})

    async def async_set_volume_level(self, volume):
        """Send volume_up command to media player."""
        await self.send_volumio_msg(
            "commands", params={"cmd": "volume", "volume": int(volume * 100)}
        )

    async def async_volume_up(self):
        """Service to send the Volumio the command for volume up."""
        await self.send_volumio_msg(
            "commands", params={"cmd": "volume", "volume": "plus"}
        )

    async def async_volume_down(self):
        """Service to send the Volumio the command for volume down."""
        await self.send_volumio_msg(
            "commands", params={"cmd": "volume", "volume": "minus"}
        )

    async def async_mute_volume(self, mute):
        """Send mute command to media player."""
        mutecmd = "mute" if mute else "unmute"
        if mute:
            # mute is implemented as 0 volume, do save last volume level
            self._lastvol = self._state["volume"]
            await self.send_volumio_msg(
                "commands", params={"cmd": "volume", "volume": mutecmd}
            )
            return

        await self.send_volumio_msg(
            "commands", params={"cmd": "volume", "volume": self._lastvol}
        )

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self.send_volumio_msg(
            "commands", params={"cmd": "random", "value": str(shuffle).lower()}
        )

    async def async_select_source(self, source):
        """Choose a different available playlist and play it."""
        self._currentplaylist = source
        await self.send_volumio_msg(
            "commands", params={"cmd": "playplaylist", "name": source}
        )

    async def async_clear_playlist(self):
        """Clear players playlist."""
        self._currentplaylist = None
        await self.send_volumio_msg("commands", params={"cmd": "clearQueue"})

    @Throttle(PLAYLIST_UPDATE_INTERVAL)
    async def _async_update_playlists(self, **kwargs):
        """Update available Volumio playlists."""
        self._playlists = await self.send_volumio_msg("listPlaylist")
