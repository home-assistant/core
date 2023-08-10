"""Support for ESPHome media players."""
from __future__ import annotations

from typing import Any

from aioesphomeapi import (
    EntityInfo,
    MediaPlayerCommand,
    MediaPlayerEntityState,
    MediaPlayerInfo,
    MediaPlayerState as EspMediaPlayerState,
)

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import (
    EsphomeEntity,
    esphome_state_property,
    platform_async_setup_entry,
)
from .enum_mapper import EsphomeEnumMapper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up esphome media players based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=MediaPlayerInfo,
        entity_type=EsphomeMediaPlayer,
        state_type=MediaPlayerEntityState,
    )


_STATES: EsphomeEnumMapper[EspMediaPlayerState, MediaPlayerState] = EsphomeEnumMapper(
    {
        EspMediaPlayerState.IDLE: MediaPlayerState.IDLE,
        EspMediaPlayerState.PLAYING: MediaPlayerState.PLAYING,
        EspMediaPlayerState.PAUSED: MediaPlayerState.PAUSED,
    }
)


class EsphomeMediaPlayer(
    EsphomeEntity[MediaPlayerInfo, MediaPlayerEntityState], MediaPlayerEntity
):
    """A media player implementation for esphome."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        flags = (
            MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        if self._static_info.supports_pause:
            flags |= MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.PLAY
        self._attr_supported_features = flags

    @property
    @esphome_state_property
    def state(self) -> MediaPlayerState | None:
        """Return current state."""
        return _STATES.from_esphome(self._state.state)

    @property
    @esphome_state_property
    def is_volume_muted(self) -> bool:
        """Return true if volume is muted."""
        return self._state.muted

    @property
    @esphome_state_property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._state.volume

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play command with media url to the media player."""
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url

        media_id = async_process_play_media_url(self.hass, media_id)

        await self._client.media_player_command(
            self._key,
            media_url=media_id,
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._client.media_player_command(self._key, volume=volume)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._client.media_player_command(
            self._key, command=MediaPlayerCommand.PAUSE
        )

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._client.media_player_command(
            self._key, command=MediaPlayerCommand.PLAY
        )

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._client.media_player_command(
            self._key, command=MediaPlayerCommand.STOP
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.MUTE if mute else MediaPlayerCommand.UNMUTE,
        )
