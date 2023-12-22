"""Media Player platform for Tessie integration."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TessieDataUpdateCoordinator
from .entity import TessieEntity

STATES = {
    "Playing": MediaPlayerState.PLAYING,
    "Paused": MediaPlayerState.PAUSED,
    "Stopped": MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie Media platform from a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(TessieMediaEntity(coordinator) for coordinator in coordinators)


class TessieMediaEntity(TessieEntity, MediaPlayerEntity):
    """Vehicle Location Media Class."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
    ) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator, "media")

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        return STATES.get(
            self.get("vehicle_state_media_info_media_playback_status"),
            MediaPlayerState.OFF,
        )

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.get("vehicle_state_media_info_audio_volume", 0) / self.get(
            "vehicle_state_media_info_audio_volume_max", 10.333333
        )

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        duration = self.get("vehicle_state_media_info_now_playing_duration")
        # Return None if duration is 0
        return duration / 1000 if duration else None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if (position := self.get("vehicle_state_media_info_now_playing_elapsed")) is not None:
            return position / 1000
        return None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        title = self.get("vehicle_state_media_info_now_playing_title")
        # Return None if title is an empty string
        return title if title else None

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        artist = self.get("vehicle_state_media_info_now_playing_artist")
        # Return None if artist is an empty string
        return artist if artist else None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        album = self.get("vehicle_state_media_info_now_playing_album")
        # Return None if album is an empty string
        return album if album else None

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        playlist = self.get("vehicle_state_media_info_now_playing_station")
        # Return None if playlist is an empty string
        return playlist if playlist else None

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        source = self.get("vehicle_state_media_info_now_playing_source")
        # Return None if source is an empty string
        return source if source else None
