"""Support to interact with a Music Player Daemon."""
from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
import hashlib
import logging
import os
from typing import Any

import mpd
from mpd.asyncio import MPDClient
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MPD"
DEFAULT_PORT = 6600

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SUPPORT_MPD = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MPD platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)

    entity = MpdDevice(host, port, password, name)
    async_add_entities([entity], True)


class MpdDevice(MediaPlayerEntity):
    """Representation of a MPD server."""

    _attr_media_content_type = MediaType.MUSIC

    # pylint: disable=no-member
    def __init__(self, server, port, password, name):
        """Initialize the MPD device."""
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
        self._muted_volume = None
        self._media_position_updated_at = None
        self._media_position = None
        self._media_image_hash = None
        # Track if the song changed so image doesn't have to be loaded every update.
        self._media_image_file = None
        self._commands = None

        # set up MPD client
        self._client = MPDClient()
        self._client.timeout = 30
        self._client.idletimeout = None

    async def _connect(self):
        """Connect to MPD."""
        try:
            await self._client.connect(self.server, self.port)

            if self.password is not None:
                await self._client.password(self.password)
        except mpd.ConnectionError:
            return

        self._is_connected = True

    def _disconnect(self):
        """Disconnect from MPD."""
        with suppress(mpd.ConnectionError):
            self._client.disconnect()
        self._is_connected = False
        self._status = None

    async def _fetch_status(self):
        """Fetch status from MPD."""
        self._status = await self._client.status()
        self._currentsong = await self._client.currentsong()
        await self._async_update_media_image_hash()

        if (position := self._status.get("elapsed")) is None:
            position = self._status.get("time")

            if isinstance(position, str) and ":" in position:
                position = position.split(":")[0]

        if position is not None and self._media_position != position:
            self._media_position_updated_at = dt_util.utcnow()
            self._media_position = int(float(position))

        await self._update_playlists()

    @property
    def available(self):
        """Return true if MPD is available and connected."""
        return self._is_connected

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        try:
            if not self._is_connected:
                await self._connect()
                self._commands = list(await self._client.commands())

            await self._fetch_status()
        except (mpd.ConnectionError, OSError, ValueError) as error:
            # Cleanly disconnect in case connection is not in valid state
            _LOGGER.debug("Error updating status: %s", error)
            self._disconnect()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> MediaPlayerState:
        """Return the media state."""
        if self._status is None:
            return MediaPlayerState.OFF
        if self._status["state"] == "play":
            return MediaPlayerState.PLAYING
        if self._status["state"] == "pause":
            return MediaPlayerState.PAUSED
        if self._status["state"] == "stop":
            return MediaPlayerState.OFF

        return MediaPlayerState.OFF

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._currentsong.get("file")

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if currentsong_time := self._currentsong.get("time"):
            return currentsong_time

        time_from_status = self._status.get("time")
        if isinstance(time_from_status, str) and ":" in time_from_status:
            return time_from_status.split(":")[1]

        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds.

        This is returned as part of the mpd status rather than in the details
        of the current song.
        """
        return self._media_position

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        return self._media_position_updated_at

    @property
    def media_title(self):
        """Return the title of current playing media."""
        name = self._currentsong.get("name", None)
        title = self._currentsong.get("title", None)
        file_name = self._currentsong.get("file", None)

        if name is None and title is None:
            if file_name is None:
                return "None"
            return os.path.basename(file_name)
        if name is None:
            return title
        if title is None:
            return name

        return f"{name}: {title}"

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        artists = self._currentsong.get("artist")
        if isinstance(artists, list):
            return ", ".join(artists)
        return artists

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return self._currentsong.get("album")

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        return self._media_image_hash

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing track."""
        if not (file := self._currentsong.get("file")):
            return None, None
        response = await self._async_get_file_image_response(file)
        if response is None:
            return None, None

        image = bytes(response["binary"])
        mime = response.get(
            "type", "image/png"
        )  # readpicture has type, albumart does not
        return (image, mime)

    async def _async_update_media_image_hash(self):
        """Update the hash value for the media image."""
        file = self._currentsong.get("file")

        if file == self._media_image_file:
            return

        if (
            file is not None
            and (response := await self._async_get_file_image_response(file))
            is not None
        ):
            self._media_image_hash = hashlib.sha256(
                bytes(response["binary"])
            ).hexdigest()[:16]
        else:
            # If there is no image, this hash has to be None, else the media player component
            # assumes there is an image and returns an error trying to load it and the
            # frontend media control card breaks.
            self._media_image_hash = None

        self._media_image_file = file

    async def _async_get_file_image_response(self, file):
        # not all MPD implementations and versions support the `albumart` and `fetchpicture` commands
        can_albumart = "albumart" in self._commands
        can_readpicture = "readpicture" in self._commands

        response = None

        # read artwork embedded into the media file
        if can_readpicture:
            try:
                response = await self._client.readpicture(file)
            except mpd.CommandError as error:
                if error.errno is not mpd.FailureResponseCode.NO_EXIST:
                    _LOGGER.warning(
                        "Retrieving artwork through `readpicture` command failed: %s",
                        error,
                    )

        # read artwork contained in the media directory (cover.{jpg,png,tiff,bmp}) if none is embedded
        if can_albumart and not response:
            try:
                response = await self._client.albumart(file)
            except mpd.CommandError as error:
                if error.errno is not mpd.FailureResponseCode.NO_EXIST:
                    _LOGGER.warning(
                        "Retrieving artwork through `albumart` command failed: %s",
                        error,
                    )

        # response can be an empty object if there is no image
        if not response:
            return None

        return response

    @property
    def volume_level(self):
        """Return the volume level."""
        if "volume" in self._status:
            return int(self._status["volume"]) / 100
        return None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self._status is None:
            return MediaPlayerEntityFeature(0)

        supported = SUPPORT_MPD
        if "volume" in self._status:
            supported |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )
        if self._playlists is not None:
            supported |= MediaPlayerEntityFeature.SELECT_SOURCE

        return supported

    @property
    def source(self):
        """Name of the current input source."""
        return self._currentplaylist

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._playlists

    async def async_select_source(self, source: str) -> None:
        """Choose a different available playlist and play it."""
        await self.async_play_media(MediaType.PLAYLIST, source)

    @Throttle(PLAYLIST_UPDATE_INTERVAL)
    async def _update_playlists(self, **kwargs: Any) -> None:
        """Update available MPD playlists."""
        try:
            self._playlists = []
            for playlist_data in await self._client.listplaylists():
                self._playlists.append(playlist_data["playlist"])
        except mpd.CommandError as error:
            self._playlists = None
            _LOGGER.warning("Playlists could not be updated: %s:", error)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume of media player."""
        if "volume" in self._status:
            await self._client.setvol(int(volume * 100))

    async def async_volume_up(self) -> None:
        """Service to send the MPD the command for volume up."""
        if "volume" in self._status:
            current_volume = int(self._status["volume"])

            if current_volume <= 100:
                self._client.setvol(current_volume + 5)

    async def async_volume_down(self) -> None:
        """Service to send the MPD the command for volume down."""
        if "volume" in self._status:
            current_volume = int(self._status["volume"])

            if current_volume >= 0:
                await self._client.setvol(current_volume - 5)

    async def async_media_play(self) -> None:
        """Service to send the MPD the command for play/pause."""
        if self._status["state"] == "pause":
            await self._client.pause(0)
        else:
            await self._client.play()

    async def async_media_pause(self) -> None:
        """Service to send the MPD the command for play/pause."""
        await self._client.pause(1)

    async def async_media_stop(self) -> None:
        """Service to send the MPD the command for stop."""
        await self._client.stop()

    async def async_media_next_track(self) -> None:
        """Service to send the MPD the command for next track."""
        await self._client.next()

    async def async_media_previous_track(self) -> None:
        """Service to send the MPD the command for previous track."""
        await self._client.previous()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute. Emulated with set_volume_level."""
        if "volume" in self._status:
            if mute:
                self._muted_volume = self.volume_level
                await self.async_set_volume_level(0)
            elif self._muted_volume is not None:
                await self.async_set_volume_level(self._muted_volume)
            self._muted = mute

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the media player the command for playing a playlist."""
        if media_source.is_media_source_id(media_id):
            media_type = MediaType.MUSIC
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        if media_type == MediaType.PLAYLIST:
            _LOGGER.debug("Playing playlist: %s", media_id)
            if media_id in self._playlists:
                self._currentplaylist = media_id
            else:
                self._currentplaylist = None
                _LOGGER.warning("Unknown playlist name %s", media_id)
            await self._client.clear()
            await self._client.load(media_id)
            await self._client.play()
        else:
            await self._client.clear()
            self._currentplaylist = None
            await self._client.add(media_id)
            await self._client.play()

    @property
    def repeat(self) -> RepeatMode:
        """Return current repeat mode."""
        if self._status["repeat"] == "1":
            if self._status["single"] == "1":
                return RepeatMode.ONE
            return RepeatMode.ALL
        return RepeatMode.OFF

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        if repeat == RepeatMode.OFF:
            await self._client.repeat(0)
            await self._client.single(0)
        else:
            await self._client.repeat(1)
            if repeat == RepeatMode.ONE:
                await self._client.single(1)
            else:
                await self._client.single(0)

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return bool(int(self._status["random"]))

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        await self._client.random(int(shuffle))

    async def async_turn_off(self) -> None:
        """Service to send the MPD the command to stop playing."""
        await self._client.stop()

    async def async_turn_on(self) -> None:
        """Service to send the MPD the command to start playing."""
        await self._client.play()
        await self._update_playlists(no_throttle=True)

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self._client.clear()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._client.seekcur(position)

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
