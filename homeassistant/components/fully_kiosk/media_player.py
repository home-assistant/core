"""Fully Kiosk Browser media player."""
from __future__ import annotations

from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerState,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUDIOMANAGER_STREAM_MUSIC, DOMAIN, MEDIA_SUPPORT_FULLYKIOSK
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser media player entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([FullyMediaPlayer(coordinator)])


class FullyMediaPlayer(FullyKioskEntity, MediaPlayerEntity):
    """Representation of a Fully Kiosk Browser media player entity."""

    _attr_supported_features = MEDIA_SUPPORT_FULLYKIOSK
    _attr_assumed_state = True

    def __init__(self, coordinator: FullyKioskDataUpdateCoordinator) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data['deviceID']}-mediaplayer"
        self._attr_state = MediaPlayerState.IDLE

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        await self.coordinator.fully.playSound(media_id, AUDIOMANAGER_STREAM_MUSIC)
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Stop playing media."""
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
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the WebSocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
