"""Media Player platform for Tessie integration."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TessieConfigEntry
from .coordinator import TessieStateUpdateCoordinator
from .entity import TessieEntity

STATES = {
    "Playing": MediaPlayerState.PLAYING,
    "Paused": MediaPlayerState.PAUSED,
    "Stopped": MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tessie Media platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(TessieMediaEntity(vehicle) for vehicle in data.vehicles)


class TessieMediaEntity(TessieEntity, MediaPlayerEntity):
    """Vehicle Location Media Class."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator,
    ) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator, "media")

    @property
    def state(self) -> MediaPlayerState:
        """State of the player."""
        return STATES.get(
            self.get("vehicle_state_media_info_media_playback_status"),
            MediaPlayerState.OFF,
        )

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self.get("vehicle_state_media_info_audio_volume", 0) / self.get(
            "vehicle_state_media_info_audio_volume_max", 10.333333
        )

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if duration := self.get("vehicle_state_media_info_now_playing_duration"):
            return duration / 1000
        return None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        # Return media position only when a media duration is > 0
        if self.get("vehicle_state_media_info_now_playing_duration"):
            return self.get("vehicle_state_media_info_now_playing_elapsed") / 1000
        return None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if title := self.get("vehicle_state_media_info_now_playing_title"):
            return title
        return None

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if artist := self.get("vehicle_state_media_info_now_playing_artist"):
            return artist
        return None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if album := self.get("vehicle_state_media_info_now_playing_album"):
            return album
        return None

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        if playlist := self.get("vehicle_state_media_info_now_playing_station"):
            return playlist
        return None

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        if source := self.get("vehicle_state_media_info_now_playing_source"):
            return source
        return None
