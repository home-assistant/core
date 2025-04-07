"""Fully Kiosk Browser media player."""

from __future__ import annotations

from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullyKioskConfigEntry
from .const import AUDIOMANAGER_STREAM_MUSIC, MEDIA_SUPPORT_FULLYKIOSK
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FullyKioskConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser media player entity."""
    coordinator = config_entry.runtime_data
    async_add_entities([FullyMediaPlayer(coordinator)])


class FullyMediaPlayer(FullyKioskEntity, MediaPlayerEntity):
    """Representation of a Fully Kiosk Browser media player entity."""

    _attr_name = None
    _attr_supported_features = MEDIA_SUPPORT_FULLYKIOSK
    _attr_assumed_state = True

    def __init__(self, coordinator: FullyKioskDataUpdateCoordinator) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data['deviceID']}-mediaplayer"
        self._attr_state = MediaPlayerState.IDLE

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        if media_type.startswith("audio/"):
            media_type = MediaType.MUSIC
        elif media_type.startswith("video/"):
            media_type = MediaType.VIDEO
        if media_type == MediaType.MUSIC:
            self._attr_media_content_type = MediaType.MUSIC
            await self.coordinator.fully.playSound(media_id, AUDIOMANAGER_STREAM_MUSIC)
        elif media_type == MediaType.VIDEO:
            self._attr_media_content_type = MediaType.VIDEO
            await self.coordinator.fully.sendCommand(
                "playVideo",
                url=media_id,
                stream=AUDIOMANAGER_STREAM_MUSIC,
                showControls=1,
                exitOnCompletion=1,
            )
        else:
            raise HomeAssistantError(f"Unsupported media type {media_type}")
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Stop playing media."""
        if self._attr_media_content_type == MediaType.VIDEO:
            await self.coordinator.fully.sendCommand("stopVideo")
        else:
            await self.coordinator.fully.stopSound()
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.fully.setAudioVolume(
            int(volume * 100), AUDIOMANAGER_STREAM_MUSIC
        )
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the WebSocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/")
            or item.media_content_type.startswith("video/"),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_state = (
            MediaPlayerState.PLAYING
            if "soundUrlPlaying" in self.coordinator.data
            else MediaPlayerState.IDLE
        )
        self.async_write_ha_state()
