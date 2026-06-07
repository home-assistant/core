"""Sandbox proxy for ``media_player`` entities."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    SearchMedia,
    SearchMediaQuery,
)

from . import SandboxProxyEntity, raise_not_proxied

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxMediaPlayerEntity(SandboxProxyEntity, MediaPlayerEntity):
    """Proxy for a ``media_player`` entity in a sandbox."""

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``MediaPlayerEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = MediaPlayerEntityFeature(
            description.supported_features or 0
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the cached state."""
        value = self._state_cache.get("state")
        if value is None or value == "unavailable":
            return None
        try:
            return MediaPlayerState(value)
        except ValueError:
            return None

    @property
    def volume_level(self) -> float | None:
        """Return the cached volume level."""
        value = self._state_cache.get(ATTR_MEDIA_VOLUME_LEVEL)
        return None if value is None else float(value)

    @property
    def is_volume_muted(self) -> bool | None:
        """Return the cached mute state."""
        value = self._state_cache.get(ATTR_MEDIA_VOLUME_MUTED)
        return None if value is None else bool(value)

    @property
    def media_content_id(self) -> str | None:
        """Return cached media_content_id."""
        return self._state_cache.get(ATTR_MEDIA_CONTENT_ID)

    @property
    def media_content_type(self) -> str | None:
        """Return cached media_content_type."""
        return self._state_cache.get(ATTR_MEDIA_CONTENT_TYPE)

    @property
    def media_duration(self) -> int | None:
        """Return cached media_duration."""
        value = self._state_cache.get(ATTR_MEDIA_DURATION)
        return None if value is None else int(value)

    @property
    def media_position(self) -> int | None:
        """Return cached media_position."""
        value = self._state_cache.get(ATTR_MEDIA_POSITION)
        return None if value is None else int(value)

    @property
    def media_title(self) -> str | None:
        """Return cached media_title."""
        return self._state_cache.get(ATTR_MEDIA_TITLE)

    @property
    def media_artist(self) -> str | None:
        """Return cached media_artist."""
        return self._state_cache.get(ATTR_MEDIA_ARTIST)

    @property
    def media_album_name(self) -> str | None:
        """Return cached media_album_name."""
        return self._state_cache.get(ATTR_MEDIA_ALBUM_NAME)

    @property
    def media_album_artist(self) -> str | None:
        """Return cached media_album_artist."""
        return self._state_cache.get(ATTR_MEDIA_ALBUM_ARTIST)

    @property
    def media_track(self) -> int | None:
        """Return cached media_track."""
        value = self._state_cache.get(ATTR_MEDIA_TRACK)
        return None if value is None else int(value)

    @property
    def source(self) -> str | None:
        """Return cached source."""
        return self._state_cache.get(ATTR_INPUT_SOURCE)

    @property
    def source_list(self) -> list[str] | None:
        """Return cached source list."""
        value = self._state_cache.get(
            ATTR_INPUT_SOURCE_LIST,
            self.description.capabilities.get(ATTR_INPUT_SOURCE_LIST),
        )
        return list(value) if value else None

    @property
    def sound_mode(self) -> str | None:
        """Return cached sound_mode."""
        return self._state_cache.get(ATTR_SOUND_MODE)

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return cached sound_mode_list."""
        value = self._state_cache.get(
            ATTR_SOUND_MODE_LIST,
            self.description.capabilities.get(ATTR_SOUND_MODE_LIST),
        )
        return list(value) if value else None

    @property
    def app_id(self) -> str | None:
        """Return cached app_id."""
        return self._state_cache.get(ATTR_APP_ID)

    @property
    def app_name(self) -> str | None:
        """Return cached app_name."""
        return self._state_cache.get(ATTR_APP_NAME)

    async def async_turn_on(self) -> None:
        """Forward turn_on."""
        await self._call_service("turn_on")

    async def async_turn_off(self) -> None:
        """Forward turn_off."""
        await self._call_service("turn_off")

    async def async_mute_volume(self, mute: bool) -> None:
        """Forward volume_mute."""
        await self._call_service("volume_mute", is_volume_muted=mute)

    async def async_set_volume_level(self, volume: float) -> None:
        """Forward volume_set."""
        await self._call_service("volume_set", volume_level=volume)

    async def async_media_play(self) -> None:
        """Forward media_play."""
        await self._call_service("media_play")

    async def async_media_pause(self) -> None:
        """Forward media_pause."""
        await self._call_service("media_pause")

    async def async_media_stop(self) -> None:
        """Forward media_stop."""
        await self._call_service("media_stop")

    async def async_media_next_track(self) -> None:
        """Forward media_next_track."""
        await self._call_service("media_next_track")

    async def async_media_previous_track(self) -> None:
        """Forward media_previous_track."""
        await self._call_service("media_previous_track")

    async def async_media_seek(self, position: float) -> None:
        """Forward media_seek."""
        await self._call_service("media_seek", seek_position=position)

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Forward play_media."""
        await self._call_service(
            "play_media",
            media_content_type=media_type,
            media_content_id=media_id,
            **kwargs,
        )

    async def async_select_source(self, source: str) -> None:
        """Forward select_source."""
        await self._call_service("select_source", source=source)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Forward select_sound_mode."""
        await self._call_service("select_sound_mode", sound_mode=sound_mode)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Raise — media browsing is a server-side query, not yet proxied."""
        raise_not_proxied("Browsing media")

    async def async_search_media(self, query: SearchMediaQuery) -> SearchMedia:
        """Raise — media search is a server-side query, not yet proxied."""
        raise_not_proxied("Searching media")

    async def async_clear_playlist(self) -> None:
        """Forward clear_playlist."""
        await self._call_service("clear_playlist")

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Forward shuffle_set."""
        await self._call_service("shuffle_set", shuffle=shuffle)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Forward repeat_set."""
        await self._call_service("repeat_set", repeat=repeat)
