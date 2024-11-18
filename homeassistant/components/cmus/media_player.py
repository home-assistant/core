"""Support for interacting with and controlling the cmus music player."""

from __future__ import annotations

import logging
from typing import Any

from pycmus import exceptions, remote
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "cmus"
DEFAULT_PORT = 3000

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Inclusive(CONF_HOST, "remote"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "remote"): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discover_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the CMUS platform."""

    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    port = config[CONF_PORT]
    name = config[CONF_NAME]

    cmus_remote = CmusRemote(server=host, port=port, password=password)
    cmus_remote.connect()

    if cmus_remote.cmus is None:
        return

    add_entities([CmusDevice(device=cmus_remote, name=name, server=host)], True)


class CmusRemote:
    """Representation of a cmus connection."""

    def __init__(self, server, port, password):
        """Initialize the cmus remote."""

        self._server = server
        self._port = port
        self._password = password
        self.cmus = None

    def connect(self):
        """Connect to the cmus server."""

        try:
            self.cmus = remote.PyCmus(
                server=self._server, port=self._port, password=self._password
            )
        except exceptions.InvalidPassword:
            _LOGGER.error("The provided password was rejected by cmus")


class CmusDevice(MediaPlayerEntity):
    """Representation of a running cmus."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.PLAY
    )

    def __init__(self, device, name, server):
        """Initialize the CMUS device."""

        self._remote = device
        if server:
            auto_name = f"cmus-{server}"
        else:
            auto_name = "cmus-local"
        self._attr_name = name or auto_name
        self.status = {}

    def update(self) -> None:
        """Get the latest data and update the state."""
        try:
            status = self._remote.cmus.get_status_dict()
        except BrokenPipeError:
            self._remote.connect()
        except exceptions.ConfigurationError:
            _LOGGER.warning("A configuration error occurred")
            self._remote.connect()
        else:
            self.status = status
            if self.status.get("status") == "playing":
                self._attr_state = MediaPlayerState.PLAYING
            elif self.status.get("status") == "paused":
                self._attr_state = MediaPlayerState.PAUSED
            else:
                self._attr_state = MediaPlayerState.OFF
            self._attr_media_content_id = self.status.get("file")
            self._attr_media_duration = self.status.get("duration")
            self._attr_media_title = self.status["tag"].get("title")
            self._attr_media_artist = self.status["tag"].get("artist")
            self._attr_media_track = self.status["tag"].get("tracknumber")
            self._attr_media_album_name = self.status["tag"].get("album")
            self._attr_media_album_artist = self.status["tag"].get("albumartist")
            left = self.status["set"].get("vol_left")[0]
            right = self.status["set"].get("vol_right")[0]
            if left != right:
                volume = float(left + right) / 2
            else:
                volume = left
            self._attr_volume_level = int(volume) / 100
            return

        _LOGGER.warning("Received no status from cmus")

    def turn_off(self) -> None:
        """Service to send the CMUS the command to stop playing."""
        self._remote.cmus.player_stop()

    def turn_on(self) -> None:
        """Service to send the CMUS the command to start playing."""
        self._remote.cmus.player_play()

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._remote.cmus.set_volume(int(volume * 100))

    def volume_up(self) -> None:
        """Set the volume up."""
        left = self.status["set"].get("vol_left")
        right = self.status["set"].get("vol_right")
        if left != right:
            current_volume = float(left + right) / 2
        else:
            current_volume = left

        if current_volume <= 100:
            self._remote.cmus.set_volume(int(current_volume) + 5)

    def volume_down(self) -> None:
        """Set the volume down."""
        left = self.status["set"].get("vol_left")
        right = self.status["set"].get("vol_right")
        if left != right:
            current_volume = float(left + right) / 2
        else:
            current_volume = left

        if current_volume <= 100:
            self._remote.cmus.set_volume(int(current_volume) - 5)

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play command."""
        if media_type in {MediaType.MUSIC, MediaType.PLAYLIST}:
            self._remote.cmus.player_play_file(media_id)
        else:
            _LOGGER.error(
                "Invalid media type %s. Only %s and %s are supported",
                media_type,
                MediaType.MUSIC,
                MediaType.PLAYLIST,
            )

    def media_pause(self) -> None:
        """Send the pause command."""
        self._remote.cmus.player_pause()

    def media_next_track(self) -> None:
        """Send next track command."""
        self._remote.cmus.player_next()

    def media_previous_track(self) -> None:
        """Send next track command."""
        self._remote.cmus.player_prev()

    def media_seek(self, position: float) -> None:
        """Send seek command."""
        self._remote.cmus.seek(position)

    def media_play(self) -> None:
        """Send the play command."""
        self._remote.cmus.player_play()

    def media_stop(self) -> None:
        """Send the stop command."""
        self._remote.cmus.stop()
