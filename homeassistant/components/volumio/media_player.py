"""
Volumio Platform.

Volumio rest API: https://volumio.github.io/docs/API/REST_API.html
"""
import asyncio
from datetime import timedelta
import logging
import socket

import aiohttp
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    SUPPORT_PLAY_MEDIA
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    HTTP_OK,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
        self._ws = None
        
        # taken from https://github.com/volumio/Volumio2/blob/master/app/plugins/user_interface/websocket/index.js
        self._methods = {
            "getDeviceInfo": "pushDeviceInfo",
            "getState":"pushState",
            "getQueue": "pushQueue",
            "getMultiRoomDevices":"pushMultiRoomDevices",
            "getLibraryListing": "pushLibraryListing",
            "getMenuItems": "pushMenuItems",
            "getUiConfig": "pushUiConfig",
            "getBrowseSources": "pushBrowseSources",
            "browseLibrary": "pushBrowseLibrary",
            "search": "pushBrowseLibrary",
            "goTo": "pushBrowseLibrary",
            "GetTrackInfo":"pushGetTrackInfo",
            "addWebRadio":"pushAddWebRadio",
            "removeWebRadio":"pushBrowseLibrary",
            "getPlaylistContent":"pushPlaylistContent",
            "createPlaylist":"pushCreatePlaylist",
            "deletePlaylist":"pushListPlaylist",
            "listPlaylist":"pushListPlaylist",
            "addToPlaylist":"pushListPlaylist",
            "removeFromPlaylist":"pushBrowseLibrary",
            "playPlaylist":"pushPlayPlaylist",
            "enqueue":"pushEnqueue",
            "addToFavourites":"urifavourites",
            "removeFromFavourites":"pushBrowseLibrary",
            "playFavourites": "pushPlayFavourites",
            "addToRadioFavourites":"pushAddToRadioFavourites",
            "removeFromRadioFavourites":"pushRemoveFromRadioFavourites",
            "playRadioFavourites":"pushPlayRadioFavourites",
            "getSleep":"pushSleep"
            
            #TODO: There are lots more, continue at L673
        }
                
    def init_websocket(self):
        """Initialize websocket, which handles all informations from / to volumio."""
        websession = async_get_clientsession(self.hass)
        url = f"ws://{self.host}:{self.port}"
        return websession.ws_connect(url)
        
    async def send_volumio_msg(self, method, params=None):
        """Handles volumio calls"""
        
        def api2websocket(method, params):
            """Transform method and params from api to websocket calls."""
            if method == "commands":
                method = params["cmd"]

                if method in params:
                    params = params[method]
                elif "value" in params:
                    params = params["value"]
                elif "name" in params:
                    params = params["name"]
                else:
                    params = params["cmd"]
                    
            return method, params
        
        method, params = api2websocket(method, params)
        
        async with self.init_websocket() as ws:
            self.send(ws, method, params)
            if method in self._methods:
                data = await self.get(ws, self._methods[method])
                _LOGGER.debug("received DATA: %s", data)
                
                return data
        return None
            
    async def get(self, ws, method):
        """Handles responses from websocket."""
        _LOGGER.debug("Get, method: %s", method)
        
        import json
        
        try:
            async for msg in ws:
                _LOGGER.debug("get, METHOD: %s, received DATA: %s", method, data)

                data = json.loads(msg.data)
                if data[0] == method:
                    return data[1]

        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error(
                "Failed communicating with Volumio '%s': %s", self._name, type(error)
            )
           
        return None

    async def send(self, ws, method, params=None):
        """Send message."""
        _LOGGER.debug("Send, method: %s params: %s", method, params)

        data = None
        
        request_data = [method]
        if params is not None:
            request_data.append(params)
        
        try:
            data = await ws.send_json(request_data)
            
            _LOGGER.debug("send METHOD: %s, received DATA: %s", method, data)
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error(
                "Failed communicating with Volumio '%s': %s", self._name, type(error)
            )

        return data

    async def async_update(self):
        """Update state."""
        resp = await self.send_volumio_msg("getState")
        await self._async_update_playlists()
        if resp is False:
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
            
    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_type == MEDIA_TYPE_PLAYLIST:
            if media_id in self._playlists:
                self._currentplaylist = media_id
            else:
                self._currentplaylist = None
                _LOGGER.warning("Unknown playlist name %s", media_id)
                
            await self.send_volumio_msg("playPlaylist", media_id)
        else:
            await self.send_volumio_msg("clearQueue")
            await self.send_volumio_msg("addToQueue", media_id)
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
