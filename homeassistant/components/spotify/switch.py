"""Support for Spotify switch entities."""

from typing import Any

from spotifyaio import ItemType

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SpotifyConfigEntry, SpotifyCoordinator
from .entity import SpotifyEntity
from .util import async_refresh_after

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpotifyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirGradient switch entities based on a config entry."""
    async_add_entities(
        [
            SpotifyLibrarySwitch(entry.runtime_data.coordinator),
        ]
    )


class SpotifyLibrarySwitch(SpotifyEntity, SwitchEntity):
    """Defines a Spotify switch entity."""

    _attr_translation_key = "library"

    def __init__(self, coordinator: SpotifyCoordinator) -> None:
        """Initialize Spotify switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.current_user.user_id}-library"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.current_playback is not None

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.coordinator.data.in_library

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.async_refresh()
        assert (
            self.coordinator.data.current_playback is not None
            and self.coordinator.data.current_playback.item is not None
        )
        if self.coordinator.data.current_playback.item.type is ItemType.TRACK:
            await self.coordinator.client.save_tracks(
                [self.coordinator.data.current_playback.item.uri]
            )
        else:
            await self.coordinator.client.save_episodes(
                [self.coordinator.data.current_playback.item.uri]
            )

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.async_refresh()
        assert (
            self.coordinator.data.current_playback is not None
            and self.coordinator.data.current_playback.item is not None
        )
        if self.coordinator.data.current_playback.item.type is ItemType.TRACK:
            await self.coordinator.client.remove_saved_tracks(
                [self.coordinator.data.current_playback.item.uri]
            )
        else:
            await self.coordinator.client.remove_saved_episodes(
                [self.coordinator.data.current_playback.item.uri]
            )
        await self.coordinator.async_request_refresh()
