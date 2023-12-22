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
        super().__init__(coordinator, "vehicle_state_media_info_media_playback_status")

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        return STATES.get(self._value, None)

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.get("vehicle_state_media_info_audio_volume") / self.get(
            "vehicle_state_media_info_audio_volume_max"
        )

    @property
    def volume_step(self) -> float:
        """Return the step to be used by the volume_up and volume_down services."""
        return self.get("vehicle_state_media_info_audio_increment") / self.get(
            "vehicle_state_media_info_audio_volume_max"
        )

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.get("vehicle_state_media_info_now_playing_duration", 0) / 1000

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self.get("vehicle_state_media_info_now_playing_elapsed", 0) / 1000

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.get("vehicle_state_media_info_now_playing_title")

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.get("vehicle_state_media_info_now_playing_artist")

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.get("vehicle_state_media_info_now_playing_album")

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        return self.get("vehicle_state_media_info_now_playing_station")

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        return self.get("vehicle_state_media_info_now_playing_source")
