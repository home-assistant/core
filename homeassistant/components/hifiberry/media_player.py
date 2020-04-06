"""
HifiBerry Platform.

HifiBerry rest API: https://github.com/hifiberry/audiocontrol2/blob/fee165140c9da044c2166cac1d77ae5e0008c351/doc/api.md
"""

from datetime import timedelta
import logging
import socket
import requests

import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
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
    STATE_PAUSED,
    STATE_PLAYING,
)

# from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

# from homeassistant.util import Throttle

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "hifiberry"
DEFAULT_NAME = "HifiBerry"
DEFAULT_PORT = 81

DATA_HIFIBERRY = "hifiberry"

TIMEOUT = 10
SCAN_INTERVAL = timedelta(seconds=1)

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
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

def setup_platform(hass, config, add_devices, discovery_info=None):
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

    device = HifiBerry(name, host, port, hass)

    hass.data[DATA_HIFIBERRY][ip_addr] = device
    add_devices([device])

class HifiBerry(MediaPlayerDevice):
    """HifiBerry Player Object."""

    def __init__(self, name, host, port, hass):
        """Initialize the media player."""
        self.host = host
        self.port = port
        self.hass = hass
        self._url = "{}:{}".format(host, str(port))
        self._name = name
        self._muted = False
        self._muted_volume = 0
        self._state = {}

    def get_hifiberry_msg(self, method, params=None):
        """Send message."""
        url = f"http://{self.host}:{self.port}/{method}"
        _LOGGER.debug("URL: %s params: %s", url, params)
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
        else:
            _LOGGER.error(
                "Query failed, response code: %s Full message: %s",
                response.status_code,
                response,
            )
            return False
        return data

    def update(self):
        """Update state."""
        resp = self.get_hifiberry_msg("api/track/metadata", None)
        if resp is False:
            return
        self._state = resp.copy()

    def post_hifiberry_msg(self, method, params=None):
        """Send message."""
        url = f"http://{self.host}:{self.port}/{method}"
        _LOGGER.debug("URL: %s params: %s", url, params)
        response = requests.post(url, json=params)
        if response.status_code == 201:
            data = response.json()
        else:
            _LOGGER.error(
                "Query failed, response code: %s Full message: %s",
                response.status_code,
                response,
            )
            return False
        return data
        self.update()

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
        url = self._state.get("artUrl", None)
        """Use remote artwork if local not available."""
        if "artwork" not in url:
            mediaurl = self._state.get("externalArtUrl", None)
        else:
            mediaurl = f"http://{self.host}:{self.port}/{url}"
        if mediaurl is None:
            return
        return mediaurl

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume_metadata = self.get_hifiberry_msg("api/volume", None)
        volume = volume_metadata.get("percent")
        if volume is not None:
            volume = int(volume) / 100
        return volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        volume = self.volume_level
        return 0 <= volume < 0.001
        # return self._muted

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

    def media_next_track(self):
        """Send media_next command to media player."""
        self.post_hifiberry_msg("api/player/next", None)

    def media_previous_track(self):
        """Send media_previous command to media player."""
        self.post_hifiberry_msg("api/player/previous", None)

    def media_play(self):
        """Send media_play command to media player."""
        self.post_hifiberry_msg("api/player/play")

    def media_pause(self):
        """Send media_pause command to media player."""
        self.post_hifiberry_msg("api/player/pause")

    def volume_up(self):
        """Service to send the hifiberry the command for volume up."""
        self.post_hifiberry_msg("api/volume", params={"percent": "+5"})

    def volume_down(self):
        """Service to send the hifiberry the command for volume down."""
        self.post_hifiberry_msg("api/volume", params={"percent": "-5"})

    def set_volume_level(self, volume):
        """Send volume_set command to media player."""
        if volume < 0:
            volume = 0
        elif volume > 1:
            volume = 1
        self.post_hifiberry_msg("api/volume", params={"percent": str(int((volume) * 100))})

    def mute_volume(self, mute):
        """Mute. Emulated with set_volume_level."""
        if mute:
            self._muted_volume = self.volume_level
            self.set_volume_level(0)
        else:
            self.set_volume_level(self._muted_volume)
        self._muted = mute
