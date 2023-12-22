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
        super().__init__(coordinator, "vehicle_state-media_info_media_playback_status")

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        state = self.get()
        if state == "Playing":
            return MediaPlayerState.PLAYING
        if state == "Paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.OFF
