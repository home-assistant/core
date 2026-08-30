"""Support for Homevolt select entities."""

from dataclasses import dataclass
from typing import override

from homevolt.const import SCHEDULE_TYPE

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomevoltConfigEntry, HomevoltDataUpdateCoordinator
from .entity import HomevoltEntity, homevolt_exception_handler

PARALLEL_UPDATES = 0  # Coordinator-based updates


@dataclass(frozen=True, kw_only=True)
class HomevoltSelectEntityDescription(SelectEntityDescription):
    """Custom (frozen) description for Homevolt select entities."""


SELECT_DESCRIPTION = HomevoltSelectEntityDescription(
    key="battery_mode",
    translation_key="battery_mode",
    entity_category=EntityCategory.CONFIG,
    has_entity_name=True,
    options=list(SCHEDULE_TYPE.values()),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Homevolt select entities."""
    coordinator = entry.runtime_data
    async_add_entities([HomevoltModeSelect(coordinator, SELECT_DESCRIPTION)])


class HomevoltModeSelect(HomevoltEntity, SelectEntity):
    """Select entity for battery operational mode."""

    entity_description: HomevoltSelectEntityDescription

    def __init__(
        self,
        coordinator: HomevoltDataUpdateCoordinator,
        description: HomevoltSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, f"ems_{coordinator.data.unique_id}")
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.unique_id}_{description.key}"
        self._attr_options = list(description.options) if description.options else []

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current selected mode."""
        mode_int = self.coordinator.client.schedule_mode
        return SCHEDULE_TYPE.get(mode_int)

    @homevolt_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        await self.coordinator.client.set_battery_mode(mode=option)
        await self.coordinator.async_request_refresh()
