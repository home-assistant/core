"""Provides helper methods for instantiating required entities."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SongpalCoordinator
from .entity import SongpalBaseEntity, SongpalSettingEntity


def create_settings_entities_for_type(
    hass: HomeAssistant,
    entry: ConfigEntry,
    instantiator: type[SongpalSettingEntity],
    setting_type: str,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create all required entities for the specified platform."""

    coordinator: SongpalCoordinator = entry.runtime_data.coordinator
    all_settings = coordinator.get_available_settings()

    new_entities: list[SongpalBaseEntity] = []
    for setting_bank, settings in all_settings.items():
        for setting in settings:
            if setting_bank == "sound_settings" and setting.target == "soundField":
                # Skipped because it's handled by the media player
                continue

            if setting.type == setting_type:
                new_entities.append(
                    instantiator(hass, coordinator, setting_bank, setting)
                )

    async_add_entities(new_entities)

    for entity in new_entities:
        entity.get_initial_state()
