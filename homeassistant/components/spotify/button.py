"""Button entity for Spotify."""

from collections.abc import Callable

from attr import dataclass
from spotifyaio import ItemType

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, SpotifyConfigEntry
from .coordinator import SpotifyCoordinator


@dataclass
class SpotifyButtonEntityDescription(ButtonEntityDescription):
    """Describes Spotify button entity."""

    press_fn: Callable[[SpotifyCoordinator], None]


async def save_current_playing_item(coordinator: SpotifyCoordinator) -> None:
    """Save the current playing item."""
    if (item := coordinator.data.item) is not None:
        if item.type is ItemType.TRACK:
            await coordinator.client.save_tracks([item.uri])
        elif item.type is ItemType.EPISODE:
            await coordinator.client.save_episodes([item.uri])


BUTTONS: tuple[SpotifyButtonEntityDescription, ...] = SpotifyButtonEntityDescription(
    key="save",
    translation_key="save",
    press_fn=save_current_playing_item,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpotifyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spotify based on a config entry."""
    data = entry.runtime_data.coordinator
    async_add_entities(SpotifyButton(data, button) for button in BUTTONS)


class SpotifyButton(CoordinatorEntity[SpotifyCoordinator], ButtonEntity):
    """Defines a Spotify button entity."""

    _attr_has_entity_name = True
    entity_description: SpotifyButtonEntityDescription

    def __init__(
        self,
        coordinator: SpotifyCoordinator,
        entity_description: SpotifyButtonEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        identifier = coordinator.current_user.user_id
        self._attr_unique_id = (
            f"{coordinator.current_user.user_id}_{entity_description.key}"
        )

        assert coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="Spotify AB",
            model=f"Spotify {coordinator.current_user.product}",
            name=f"Spotify {coordinator.config_entry.title}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.spotify.com",
        )

    async def async_press(self) -> None:
        """Press the button."""
        self.entity_description.press_fn(self.coordinator)
