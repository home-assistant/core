"""Provides helper methods for instantiating required entities."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import IntegrationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import SongpalBaseEntity


def create_entities_for_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    instantiator: type[SongpalBaseEntity],
    platform: str,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create all required entities for the specified platform."""
    coordinator = entry.runtime_data.coordinator

    new_entities: list[SongpalBaseEntity]
    match platform:
        case "media_player":
            new_entities = [instantiator(hass, coordinator)]
        case _:
            raise IntegrationError(
                f"Attempt to create entities for unknown platform '{platform}'"
            )

    async_add_entities(new_entities)

    for entity in new_entities:
        entity.get_initial_state()
