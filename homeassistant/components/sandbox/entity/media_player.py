"""Sandbox proxy for media_player entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxMediaPlayerEntity(SandboxProxyEntity, MediaPlayerEntity):
    """Proxy for a media_player entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy media player entity."""
        super().__init__(description, manager)
        self._attr_supported_features = MediaPlayerEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if source_list := caps.get("source_list"):
            self._attr_source_list = source_list
        if sound_mode_list := caps.get("sound_mode_list"):
            self._attr_sound_mode_list = sound_mode_list

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return MediaPlayerState(state)

    @property
    def volume_level(self) -> float | None:
        """Return the volume level."""
        return self._state_cache.get("volume_level")

    @property
    def is_volume_muted(self) -> bool | None:
        """Return if volume is muted."""
        return self._state_cache.get("is_volume_muted")

    @property
    def media_content_id(self) -> str | None:
        """Return the media content ID."""
        return self._state_cache.get("media_content_id")

    @property
    def media_content_type(self) -> str | None:
        """Return the media content type."""
        return self._state_cache.get("media_content_type")

    @property
    def media_title(self) -> str | None:
        """Return the media title."""
        return self._state_cache.get("media_title")

    @property
    def media_artist(self) -> str | None:
        """Return the media artist."""
        return self._state_cache.get("media_artist")

    @property
    def media_album_name(self) -> str | None:
        """Return the media album name."""
        return self._state_cache.get("media_album_name")

    @property
    def media_duration(self) -> float | None:
        """Return the media duration."""
        return self._state_cache.get("media_duration")

    @property
    def media_position(self) -> float | None:
        """Return the media position."""
        return self._state_cache.get("media_position")

    @property
    def source(self) -> str | None:
        """Return the current source."""
        return self._state_cache.get("source")

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        return self._state_cache.get("sound_mode")

    @property
    def shuffle(self) -> bool | None:
        """Return if shuffle is enabled."""
        return self._state_cache.get("shuffle")

    @property
    def repeat(self) -> RepeatMode | None:
        """Return the current repeat mode."""
        val = self._state_cache.get("repeat")
        if val is None:
            return None
        return RepeatMode(val)

    async def async_turn_on(self) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on")

    async def async_turn_off(self) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off")

    async def async_volume_up(self) -> None:
        """Forward volume_up to sandbox."""
        await self._forward_method("async_volume_up")

    async def async_volume_down(self) -> None:
        """Forward volume_down to sandbox."""
        await self._forward_method("async_volume_down")

    async def async_set_volume_level(self, volume: float) -> None:
        """Forward set_volume_level to sandbox."""
        await self._forward_method("async_set_volume_level", volume=volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Forward mute_volume to sandbox."""
        await self._forward_method("async_mute_volume", mute=mute)

    async def async_media_play(self) -> None:
        """Forward media_play to sandbox."""
        await self._forward_method("async_media_play")

    async def async_media_pause(self) -> None:
        """Forward media_pause to sandbox."""
        await self._forward_method("async_media_pause")

    async def async_media_stop(self) -> None:
        """Forward media_stop to sandbox."""
        await self._forward_method("async_media_stop")

    async def async_media_next_track(self) -> None:
        """Forward media_next_track to sandbox."""
        await self._forward_method("async_media_next_track")

    async def async_media_previous_track(self) -> None:
        """Forward media_previous_track to sandbox."""
        await self._forward_method("async_media_previous_track")

    async def async_media_seek(self, position: float) -> None:
        """Forward media_seek to sandbox."""
        await self._forward_method("async_media_seek", position=position)

    async def async_select_source(self, source: str) -> None:
        """Forward select_source to sandbox."""
        await self._forward_method("async_select_source", source=source)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Forward select_sound_mode to sandbox."""
        await self._forward_method("async_select_sound_mode", sound_mode=sound_mode)

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Forward play_media to sandbox."""
        await self._forward_method("async_play_media", media_type=media_type, media_id=media_id, **kwargs)
