"""Provide functionality to interact with the vlc telnet interface."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, TypeVar
from urllib.parse import quote

from aiovlc.client import Client
from aiovlc.exceptions import AuthError, CommandError, ConnectError
from typing_extensions import Concatenate, ParamSpec
import yarl

from homeassistant.components import media_source
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import BrowseMedia, MediaPlayerEntity
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
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url, is_hass_url
import homeassistant.util.dt as dt_util

from .const import DATA_AVAILABLE, DATA_VLC, DEFAULT_NAME, DOMAIN, LOGGER

MAX_VOLUME = 500

SUPPORT_VLC = (
    SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SEEK
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_STOP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_BROWSE_MEDIA
)

_T = TypeVar("_T", bound="VlcDevice")
_R = TypeVar("_R")
_P = ParamSpec("_P")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the vlc platform."""
    # CONF_NAME is only present in imported YAML.
    name = entry.data.get(CONF_NAME) or DEFAULT_NAME
    vlc = hass.data[DOMAIN][entry.entry_id][DATA_VLC]
    available = hass.data[DOMAIN][entry.entry_id][DATA_AVAILABLE]

    async_add_entities([VlcDevice(entry, vlc, name, available)], True)


def catch_vlc_errors(
    func: Callable[Concatenate[_T, _P], Awaitable[None]]  # type: ignore[misc]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:  # type: ignore[misc]
    """Catch VLC errors."""

    @wraps(func)
    async def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Catch VLC errors and modify availability."""
        try:
            await func(self, *args, **kwargs)
        except CommandError as err:
            LOGGER.error("Command error: %s", err)
        except ConnectError as err:
            # pylint: disable=protected-access
            if self._available:
                LOGGER.error("Connection error: %s", err)
                self._available = False

    return wrapper


class VlcDevice(MediaPlayerEntity):
    """Representation of a vlc player."""

    def __init__(
        self, config_entry: ConfigEntry, vlc: Client, name: str, available: bool
    ) -> None:
        """Initialize the vlc device."""
        self._config_entry = config_entry
        self._name = name
        self._volume: float | None = None
        self._muted: bool | None = None
        self._state: str | None = None
        self._media_position_updated_at: datetime | None = None
        self._media_position: int | None = None
        self._media_duration: int | None = None
        self._vlc = vlc
        self._available = available
        self._volume_bkp = 0.0
        self._media_artist: str | None = None
        self._media_title: str | None = None
        config_entry_id = config_entry.entry_id
        self._attr_unique_id = config_entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry_id)},
            manufacturer="VideoLAN",
            name=name,
        )

    @catch_vlc_errors
    async def async_update(self) -> None:
        """Get the latest details from the device."""
        if not self._available:
            try:
                await self._vlc.connect()
            except ConnectError as err:
                LOGGER.debug("Connection error: %s", err)
                return

            try:
                await self._vlc.login()
            except AuthError:
                LOGGER.debug("Failed to login to VLC")
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._config_entry.entry_id)
                )
                return

            self._state = STATE_IDLE
            self._available = True
            LOGGER.info("Connected to vlc host: %s", self._vlc.host)

        status = await self._vlc.status()
        LOGGER.debug("Status: %s", status)

        self._volume = status.audio_volume / MAX_VOLUME
        state = status.state
        if state == "playing":
            self._state = STATE_PLAYING
        elif state == "paused":
            self._state = STATE_PAUSED
        else:
            self._state = STATE_IDLE

        if self._state != STATE_IDLE:
            self._media_duration = (await self._vlc.get_length()).length
            time_output = await self._vlc.get_time()
            vlc_position = time_output.time

            # Check if current position is stale.
            if vlc_position != self._media_position:
                self._media_position_updated_at = dt_util.utcnow()
                self._media_position = vlc_position

        info = await self._vlc.info()
        data = info.data
        LOGGER.debug("Info data: %s", data)

        self._media_artist = data.get(0, {}).get("artist")
        self._media_title = data.get(0, {}).get("title")

        if self._media_title:
            return

        # Fall back to filename.
        if data_info := data.get("data"):
            self._media_title = data_info["filename"]

            # Strip out auth signatures if streaming local media
            if self._media_title and (pos := self._media_title.find("?authSig=")) != -1:
                self._media_title = self._media_title[:pos]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return SUPPORT_VLC

    @property
    def media_content_type(self) -> str:
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._media_title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._media_artist

    @catch_vlc_errors
    async def async_media_seek(self, position: float) -> None:
        """Seek the media to a specific location."""
        await self._vlc.seek(round(position))

    @catch_vlc_errors
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        assert self._volume is not None
        if mute:
            self._volume_bkp = self._volume
            await self.async_set_volume_level(0)
        else:
            await self.async_set_volume_level(self._volume_bkp)

        self._muted = mute

    @catch_vlc_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._vlc.set_volume(round(volume * MAX_VOLUME))
        self._volume = volume

        if self._muted and self._volume > 0:
            # This can happen if we were muted and then see a volume_up.
            self._muted = False

    @catch_vlc_errors
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._vlc.play()
        self._state = STATE_PLAYING

    @catch_vlc_errors
    async def async_media_pause(self) -> None:
        """Send pause command."""
        status = await self._vlc.status()
        if status.state != "paused":
            # Make sure we're not already paused since VLCTelnet.pause() toggles
            # pause.
            await self._vlc.pause()

        self._state = STATE_PAUSED

    @catch_vlc_errors
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._vlc.stop()
        self._state = STATE_IDLE

    @catch_vlc_errors
    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media from a URL or file."""
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(self.hass, media_id)
            media_type = sourced_media.mime_type
            media_id = sourced_media.url

        if media_type != MEDIA_TYPE_MUSIC and not media_type.startswith("audio/"):
            raise HomeAssistantError(
                f"Invalid media type {media_type}. Only {MEDIA_TYPE_MUSIC} is supported"
            )

        # Sign and prefix with URL if playing a relative URL
        if media_id[0] == "/" or is_hass_url(self.hass, media_id):
            parsed = yarl.URL(media_id)

            if parsed.query:
                LOGGER.debug("Not signing path for content with query param")
            else:
                media_id = async_sign_path(
                    self.hass,
                    quote(media_id),
                    timedelta(seconds=media_source.DEFAULT_EXPIRY_TIME),
                )

            # prepend external URL
            if media_id[0] == "/":
                media_id = f"{get_url(self.hass)}{media_id}"

        await self._vlc.add(media_id)
        self._state = STATE_PLAYING

    @catch_vlc_errors
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._vlc.prev()

    @catch_vlc_errors
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._vlc.next()

    @catch_vlc_errors
    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self._vlc.clear()

    @catch_vlc_errors
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        shuffle_command = "on" if shuffle else "off"
        await self._vlc.random(shuffle_command)

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
