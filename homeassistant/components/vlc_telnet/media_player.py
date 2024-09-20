"""Provide functionality to interact with the vlc telnet interface."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, Literal

from aiovlc.client import Client
from aiovlc.exceptions import AuthError, CommandError, ConnectError

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import SOURCE_HASSIO, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import VlcConfigEntry
from .const import DEFAULT_NAME, DOMAIN, LOGGER

MAX_VOLUME = 500


def _get_str(data: dict, key: str) -> str | None:
    """Get a value from a dictionary and cast it to a string or None."""
    if value := data.get(key):
        return str(value)
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: VlcConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the vlc platform."""
    # CONF_NAME is only present in imported YAML.
    name = entry.data.get(CONF_NAME) or DEFAULT_NAME
    vlc = entry.runtime_data.vlc
    available = entry.runtime_data.available

    async_add_entities([VlcDevice(entry, vlc, name, available)], True)


def catch_vlc_errors[_VlcDeviceT: VlcDevice, **_P](
    func: Callable[Concatenate[_VlcDeviceT, _P], Awaitable[None]],
) -> Callable[Concatenate[_VlcDeviceT, _P], Coroutine[Any, Any, None]]:
    """Catch VLC errors."""

    @wraps(func)
    async def wrapper(self: _VlcDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Catch VLC errors and modify availability."""
        try:
            await func(self, *args, **kwargs)
        except CommandError as err:
            LOGGER.error("Command error: %s", err)
        except ConnectError as err:
            if self._attr_available:
                LOGGER.error("Connection error: %s", err)
                self._attr_available = False

    return wrapper


class VlcDevice(MediaPlayerEntity):
    """Representation of a vlc player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.CLEAR_PLAYLIST
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    _volume_bkp = 0.0
    volume_level: int

    def __init__(
        self, config_entry: ConfigEntry, vlc: Client, name: str, available: bool
    ) -> None:
        """Initialize the vlc device."""
        self._config_entry = config_entry
        self._vlc = vlc
        self._attr_available = available
        config_entry_id = config_entry.entry_id
        self._attr_unique_id = config_entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry_id)},
            manufacturer="VideoLAN",
            name=name,
        )
        self._using_addon = config_entry.source == SOURCE_HASSIO

    @catch_vlc_errors
    async def async_update(self) -> None:
        """Get the latest details from the device."""
        if not self.available:
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

            self._attr_state = MediaPlayerState.IDLE
            self._attr_available = True
            LOGGER.debug("Connected to vlc host: %s", self._vlc.host)

        status = await self._vlc.status()
        LOGGER.debug("Status: %s", status)

        self._attr_volume_level = status.audio_volume / MAX_VOLUME
        state = status.state
        if state == "playing":
            self._attr_state = MediaPlayerState.PLAYING
        elif state == "paused":
            self._attr_state = MediaPlayerState.PAUSED
        else:
            self._attr_state = MediaPlayerState.IDLE

        if self._attr_state != MediaPlayerState.IDLE:
            self._attr_media_duration = (await self._vlc.get_length()).length
            time_output = await self._vlc.get_time()
            vlc_position = time_output.time

            # Check if current position is stale.
            if vlc_position != self.media_position:
                self._attr_media_position_updated_at = dt_util.utcnow()
                self._attr_media_position = vlc_position

        info = await self._vlc.info()
        data = info.data
        LOGGER.debug("Info data: %s", data)

        self._attr_media_album_name = _get_str(data.get("data", {}), "album")
        self._attr_media_artist = _get_str(data.get("data", {}), "artist")
        self._attr_media_title = _get_str(data.get("data", {}), "title")
        now_playing = _get_str(data.get("data", {}), "now_playing")

        # Many radio streams put artist/title/album in now_playing and title is the station name.
        if now_playing:
            if not self.media_artist:
                self._attr_media_artist = self._attr_media_title
            self._attr_media_title = now_playing

        if self.media_title:
            return

        # Fall back to filename.
        if data_info := data.get("data"):
            self._attr_media_title = _get_str(data_info, "filename")

            # Strip out auth signatures if streaming local media
            if (media_title := self.media_title) and (
                pos := media_title.find("?authSig=")
            ) != -1:
                self._attr_media_title = media_title[:pos]

    @catch_vlc_errors
    async def async_media_seek(self, position: float) -> None:
        """Seek the media to a specific location."""
        await self._vlc.seek(round(position))

    @catch_vlc_errors
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        assert self._attr_volume_level is not None
        if mute:
            self._volume_bkp = self._attr_volume_level
            await self.async_set_volume_level(0)
        else:
            await self.async_set_volume_level(self._volume_bkp)

        self._attr_is_volume_muted = mute

    @catch_vlc_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._vlc.set_volume(round(volume * MAX_VOLUME))
        self._attr_volume_level = volume

        if self.is_volume_muted and self.volume_level > 0:
            # This can happen if we were muted and then see a volume_up.
            self._attr_is_volume_muted = False

    @catch_vlc_errors
    async def async_media_play(self) -> None:
        """Send play command."""
        status = await self._vlc.status()
        if status.state == "paused":
            # If already paused, play by toggling pause.
            await self._vlc.pause()
        else:
            await self._vlc.play()
        self._attr_state = MediaPlayerState.PLAYING

    @catch_vlc_errors
    async def async_media_pause(self) -> None:
        """Send pause command."""
        status = await self._vlc.status()
        if status.state != "paused":
            # Make sure we're not already paused as pausing again will unpause.
            await self._vlc.pause()

        self._attr_state = MediaPlayerState.PAUSED

    @catch_vlc_errors
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._vlc.stop()
        self._attr_state = MediaPlayerState.IDLE

    @catch_vlc_errors
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media from a URL or file."""
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url

        # If media ID is a relative URL, we serve it from HA.
        media_id = async_process_play_media_url(
            self.hass, media_id, for_supervisor_network=self._using_addon
        )

        await self._vlc.add(media_id)
        self._attr_state = MediaPlayerState.PLAYING

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
        shuffle_command: Literal["on", "off"] = "on" if shuffle else "off"
        await self._vlc.random(shuffle_command)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(self.hass, media_content_id)
