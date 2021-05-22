"""Support for System Bridge media player."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging

from systembridge import Bridge
from systembridge.objects.events import Event

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TRACK,
    MEDIA_TYPE_TVSHOW,
    MEDIA_TYPE_VIDEO,
    SUPPORT_BROWSE_MEDIA,
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
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING
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

    async_add_entities(
        [BridgeAudio(coordinator, bridge), BridgeMediaPlayer(coordinator, bridge)]
    )


class BridgeAudio(BridgeDeviceEntity, MediaPlayerEntity):
    """Defines a System Bridge media player."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge) -> None:
        """Initialize System Bridge media player."""
        super().__init__(coordinator, bridge, "audio", "Audio", None, True)

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP

    @property
    def state(self) -> str:
        """State of the player."""
        return STATE_PLAYING

    @property
    def media_content_type(self) -> str:
        """Content type of current playing media."""
        return MEDIA_TYPE_APP

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        bridge: Bridge = self.coordinator.data
        if bridge.audio is None or bridge.audio.attributes is None:
            return None
        return bridge.audio.current["volume"] / 100

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        bridge: Bridge = self.coordinator.data
        if bridge.audio is None or bridge.audio.attributes is None:
            return None
        return bridge.audio.current["muted"]

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_audio("mute", {"value": mute})
        await self.coordinator.async_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        bridge: Bridge = self.coordinator.data
        await bridge.async_update_audio("volume", {"value": volume * 100})
        await self.coordinator.async_refresh()


class BridgeMediaPlayer(BridgeDeviceEntity, MediaPlayerEntity):
    """Defines a System Bridge media player."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge) -> None:
        """Initialize System Bridge media player."""
        super().__init__(
            coordinator, bridge, "media_player", "Media Player", None, True
        )

        async def handle_event(event: Event) -> None:
            if event.name == "player-status":
                await self.async_update_ha_state()

        # TODO: Reconnect on disconnect/error (in package? / in refresh)
        asyncio.ensure_future(bridge.listen_for_events(handle_event))

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return (
            SUPPORT_BROWSE_MEDIA
            | SUPPORT_PAUSE
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
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return STATE_IDLE
        if bridge.media_status.playing is True:
            return STATE_PLAYING
        else:
            return STATE_PAUSED

    @property
    def media_content_type(self) -> str | None:
        """Content type of current playing media."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        if bridge.media_status.source["type"] == "audio":
            return MEDIA_TYPE_MUSIC
        elif bridge.media_status.source["type"] == "video":
            return MEDIA_TYPE_VIDEO
        return None

    @property
    def media_duration(self) -> float | None:
        """Duration of current playing media in seconds."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        return bridge.media_status.duration

    @property
    def media_position(self) -> float | None:
        """Position of current playing media in seconds."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        return bridge.media_status.position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid."""
        bridge: Bridge = self.coordinator.data
        return bridge.media_status_last_updated

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        return bridge.media_status.volume

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        return bridge.media_status.muted

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        bridge: Bridge = self.coordinator.data
        if (
            bridge.media_status is None
            or bridge.media_status.attributes is None
            or not bridge.media_status.has_cover
        ):
            return None
        return bridge.media_cover_url

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        return bridge.media_status.source.get("title")

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        return bridge.media_status.source.get("artist")

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        bridge: Bridge = self.coordinator.data
        if bridge.media_status is None or bridge.media_status.attributes is None:
            return None
        return bridge.media_status.source.get("album")

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

    # TODO: Handle browse media
    # async def async_browse_media(
    #     self,
    #     media_content_type: str | None = None,
    #     media_content_id: str | None = None,
    # ) -> BrowseMedia:
    #     """Return a BrowseMedia instance."""
    #     if media_content_id is None:
    #         raise
    #     return await media_source.async_browse_media(self.hass, media_content_id)

    async def async_play_media(self, media_type: str, media_id: str, **kwargs):
        """Play a piece of media."""
        # TODO: Handle browse media urls

        bridge: Bridge = self.coordinator.data
        if media_type in [MEDIA_TYPE_MUSIC, MEDIA_TYPE_TRACK]:
            if "/tts" in media_id:
                await bridge.async_create_media_player(
                    {"type": "audio", "url": media_id, "hidden": True}
                )
            else:
                await bridge.async_create_media_player(
                    {"type": "audio", "url": media_id}
                )
        elif media_type in [
            MEDIA_TYPE_EPISODE,
            MEDIA_TYPE_MOVIE,
            MEDIA_TYPE_TVSHOW,
            MEDIA_TYPE_VIDEO,
        ]:
            await bridge.async_create_media_player({"type": "video", "url": media_id})
