"""Provides helper methods for instantiating required entities."""

from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SongpalCoordinator
from .entity import SongpalBaseEntity, SongpalSettingEntity


def create_entities_for_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    instantiator: type[SongpalBaseEntity],
    platform: str,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create all required entities for the specified platform."""
    new_entities = get_entities_for_platform(hass, entry, instantiator, platform)

    async_add_entities(new_entities)

    for entity in new_entities:
        entity.get_initial_state()


def get_entities_for_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    instantiator: type[SongpalBaseEntity],
    platform: str,
) -> list[SongpalBaseEntity]:
    """Get required entities to add for specified platform."""

    coordinator: SongpalCoordinator = entry.runtime_data.coordinator

    if platform == "media_player":
        return [instantiator(hass, coordinator)]

    setting_instantiator = cast(type[SongpalSettingEntity], instantiator)

    all_settings = coordinator.get_available_settings()

    new_entities: list[SongpalBaseEntity] = []
    for setting_bank, settings in all_settings.items():
        for setting in settings:
            if setting_bank == "sound_settings" and setting.target == "soundField":
                continue

            if setting.type == "booleanTarget":
                new_entities.append(
                    setting_instantiator(
                        hass, coordinator, setting_bank, setting.target
                    )
                )

    return new_entities
