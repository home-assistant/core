"""Provides helper methods for instantiating required entities."""

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SongpalConfigEntry, SongpalCoordinator
from .entity import SongpalBaseEntity, SongpalSettingEntity


def create_settings_entities_for_type(
    entry: SongpalConfigEntry,
    instantiator: type[SongpalSettingEntity],
    setting_type: str,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create all required entities for the specified platform."""

    coordinator: SongpalCoordinator = entry.runtime_data
    all_settings = coordinator.get_available_settings()

    new_entities: list[SongpalBaseEntity] = []
    for setting_bank, settings in all_settings.items():
        new_entities.extend(
            [
                instantiator(coordinator, setting_bank, setting)
                for setting in settings
                if setting.type == setting_type
            ]
        )

    async_add_entities(new_entities)

    for entity in new_entities:
        entity.get_initial_state()
