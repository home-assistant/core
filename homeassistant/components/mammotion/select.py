from dataclasses import dataclass
from typing import Awaitable, Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymammotion.data.model.mowing_modes import (
    BorderPatrolMode,
    CuttingMode,
    MowOrder,
    ObstacleLapsMode,
)

from . import MammotionConfigEntry
from .coordinator import MammotionDataUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionSelectEntityDescription(SelectEntityDescription):
    """Describes Mammotion select entity."""

    key: str
    options: list[str]


SELECT_ENTITIES: tuple[MammotionSelectEntityDescription, ...] = (
    MammotionSelectEntityDescription(
        key="cutting_mode",
        entity_category=EntityCategory.CONFIG,
        options=[mode.name for mode in CuttingMode]
    ),
    MammotionSelectEntityDescription(
        key="border_patrol_mode",
        entity_category=EntityCategory.CONFIG,
        options=[mode.name for mode in BorderPatrolMode]
    ),
    MammotionSelectEntityDescription(
        key="obstacle_laps_mode",
        entity_category=EntityCategory.CONFIG,
        options=[mode.name for mode in ObstacleLapsMode]
    ),
    MammotionSelectEntityDescription(
        key="mow_order",
        entity_category=EntityCategory.CONFIG,
        options=[order.name for order in MowOrder]
    ),
)


# Define the setup entry function
async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mammotion select entity."""
    coordinator = entry.runtime_data

    async_add_entities(
        MammotionSelectEntity(coordinator, entity_description)
        for entity_description in SELECT_ENTITIES
    )


# Define the select entity class with entity_category: config
class MammotionSelectEntity(MammotionBaseEntity, SelectEntity):
    """Representation of a Mammotion select entities."""

    _attr_entity_category = EntityCategory.CONFIG

    entity_description: MammotionSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        entity_description: MammotionSelectEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._attr_options = entity_description.options
        self._attr_current_option = entity_description.options[0]
