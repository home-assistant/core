"""
HifiBerry Platform.

HifiBerry rest API: https://github.com/hifiberry/audiocontrol2/blob/fee165140c9da044c2166cac1d77ae5e0008c351/doc/api.md
"""
import asyncio
from asyncio import CancelledError
from datetime import timedelta
import logging
import socket

import aiohttp
from aiohttp.client_exceptions import ClientError
from aiohttp.hdrs import CONNECTION, KEEP_ALIVE
import async_timeout
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
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
    HTTP_OK,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "HifiBerry"
DEFAULT_PORT = 81

DATA_HIFIBERRY = "hifiberry"

TIMEOUT = 10
SCAN_INTERVAL = timedelta(seconds=2)

SUPPORT_HIFIBERRY = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_STOP
    | SUPPORT_PLAY
    | SUPPORT_VOLUME_STEP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HifiBerry platform."""
    if DATA_HIFIBERRY not in hass.data:
        hass.data[DATA_HIFIBERRY] = dict()

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
    if ip_addr in hass.data[DATA_HIFIBERRY]:
        return

    entity = HifiBerry(name, host, port, hass)

    hass.data[DATA_HIFIBERRY][ip_addr] = entity
    async_add_entities([entity])


class HifiBerry(MediaPlayerEntity):
    """HifiBerry Player Object."""

    def __init__(self, name, host, port, hass):
        """Initialize the media player."""
        self.host = host
        self.port = port
        self.hass = hass
        self._url = "{}:{}".format(host, str(port))
        self._name = name
        self._muted = False
        self._state = {}
        self._volume = {}
        self._muted_volume = self.volume_level

    async def get_hifiberry_msg(self, method, params=None):
        """Send message."""
        url = f"http://{self.host}:{self.port}/{method}"
        _LOGGER.debug("URL: %s params: %s", url, params)
        
        try:
            websession = async_get_clientsession(self.hass)
            response = await websession.get(url)
            if response.status == HTTP_OK:
                data = await response.json(content_type=None)
            else:
                _LOGGER.error(
                    "Get failed, response code: %s Full message: %s",
                    response.status,
                    response,
                )
                return False

        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error(
                "Failed communicating with HifiBerry '%s': %s", self._name, type(error)
            )
            return False
        return data

    async def post_hifiberry_msg(self, method, params=None):
        """Send message."""
        url = f"http://{self.host}:{self.port}/{method}"
        _LOGGER.debug("URL: %s params: %s", url, params)
        
        try:
            websession = async_get_clientsession(self.hass)
            response = await websession.post(url, json=params)
            if response.status == HTTP_OK:
                data = await response.json()
            else:
                _LOGGER.error(
                    "Post failed, response code: %s Full message: %s",
                    response.status,
                    response,
                )
                return False

        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error(
                "Failed communicating with HifiBerry '%s': %s", self._name, type(error)
            )
            return False
        return data

    async def async_update_volume(self):
        """Update volume level."""
        resp = await self.get_hifiberry_msg("api/volume", None)
        if resp is False:
            return
        self._volume = resp.copy()

    async def async_update(self):
        """Update state."""
        resp = await self.get_hifiberry_msg("api/track/metadata", None)
        await self.async_update_volume()
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
        status = self._state.get("playerState", None)
        if status == "paused":
            return STATE_PAUSED
        if status == "playing":
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
        return self._state.get("albumTitle", None)

    @property
    def media_image_url(self):
            """Image url of current playing media."""
            artUrl = self._state.get("artUrl", None)
            externalArtUrl = self._state.get("externalArtUrl", None)
            if artUrl is not None:
                if artUrl.startswith("static/"):
                    return externalArtUrl
                if artUrl.startswith("artwork/"):
                    return f"http://{self.host}:{self.port}/{artUrl}"
                return artUrl
            return externalArtUrl

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume = self._volume.get("percent")
        if volume is not None:
            volume = int(volume) / 100
        return volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def source(self):
        """Name of the current input source."""
        return self._state.get("playerName")

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_HIFIBERRY

    async def async_media_next_track(self):
        """Send media_next command to media player."""
        await self.post_hifiberry_msg("api/player/next", None)

    async def async_media_previous_track(self):
        """Send media_previous command to media player."""
        await self.post_hifiberry_msg("api/player/previous", None)

    async def async_media_play(self):
        """Send media_play command to media player."""
        await self.post_hifiberry_msg("api/player/play")

    async def async_media_pause(self):
        """Send media_pause command to media player."""
        await self.post_hifiberry_msg("api/player/pause")

    async def async_volume_up(self):
        """Service to send the hifiberry the command for volume up."""
        await self.post_hifiberry_msg("api/volume", params={"percent": "+5"})

    async def async_volume_down(self):
        """Service to send the hifiberry the command for volume down."""
        await self.post_hifiberry_msg("api/volume", params={"percent": "-5"})

    async def async_set_volume_level(self, volume):
        """Send volume_set command to media player."""
        if volume < 0:
            volume = 0
        elif volume > 1:
            volume = 1
        await self.post_hifiberry_msg(
            "api/volume", params={"percent": str(int((volume) * 100))}
        )

    async def async_mute_volume(self, mute):
        """Mute. Emulated with set_volume_level."""
        if mute:
            self._muted_volume = self.volume_level
            await self.post_hifiberry_msg("api/volume", params={"percent": str(int((0) * 100))})
        await self.post_hifiberry_msg("api/volume", params={"percent": str(int((self._muted_volume) * 100))})
        self._muted = mute