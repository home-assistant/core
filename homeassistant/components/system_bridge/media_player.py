"""Support for System Bridge media player."""
from __future__ import annotations

import asyncio
import logging

from systembridge import Bridge
from systembridge.objects.events import Event
from systembridge.objects.media import Media

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_VIDEO,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_SEEK,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import BridgeDeviceEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge media player based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    bridge: Bridge = coordinator.data

    for setting in bridge.settings:
        if setting.key == "wsPort":
            ws_port = setting.value

    await bridge.async_connect_websocket(entry.data[CONF_HOST], ws_port)

    async_add_entities([BridgeMediaPlayer(coordinator, bridge)])


class BridgeMediaPlayer(BridgeDeviceEntity, MediaPlayerEntity):
    """Defines a System Bridge media player."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge) -> None:
        """Initialize System Bridge media player."""
        super().__init__(
            coordinator, bridge, "media_player", "Media Player", None, True
        )
        self._media_player_status: Media = None

        async def handle_event(event: Event) -> None:
            if event.name == "player-status":
                self._media_player_status = Media(event.data)
                await self.async_update_ha_state()

        asyncio.ensure_future(bridge.listen_for_events(handle_event))

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return (
            SUPPORT_PAUSE
            | SUPPORT_PLAY
            | SUPPORT_PLAY_MEDIA
            | SUPPORT_SEEK
            | SUPPORT_STOP
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
        )

    @property
    def state(self) -> str:
        """State of the player."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return STATE_IDLE
        if self._media_player_status.playing is True:
            return STATE_PLAYING
        else:
            return STATE_PAUSED

    @property
    def media_content_type(self) -> str | None:
        """Content type of current playing media."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        if self._media_player_status.source["type"] == "audio":
            return MEDIA_TYPE_MUSIC
        elif self._media_player_status.source["type"] == "video":
            return MEDIA_TYPE_VIDEO
        return None

    @property
    def media_duration(self) -> float | None:
        """Duration of current playing media in seconds."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        return self._media_player_status.duration

    @property
    def media_position(self) -> float | None:
        """Position of current playing media in seconds."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        return self._media_player_status.position

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        return self._media_player_status.volume

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        return self._media_player_status.muted

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        # TODO: Add get cover method to package
        return None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        return self._media_player_status.source.get("title")

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        return self._media_player_status.source.get("artist")

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if (
            self._media_player_status is None
            or self._media_player_status.attributes is None
        ):
            return None
        return self._media_player_status.source.get("album")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_media("mute", {"value": mute})

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_media("volume", {"value": volume * 100})

    async def async_media_play(self) -> None:
        """Send play command."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_media("play", None)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_media("pause", None)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_media("stop", None)

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_media("seek", {"value": position})
