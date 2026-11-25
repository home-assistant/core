"""Select entities for Daikin."""

from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DAIKIN_DEMAND_CONTROL_OPTIONS
from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .demand_control import (
    async_select_demand_control_option,
    get_demand_control_option,
)
from .entity import DaikinEntity, daikin_exception_handler

DEMAND_CONTROL_MODE = SelectEntityDescription(
    key="demand_control",
    translation_key="demand_control_mode",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin select entities."""
    coordinator = entry.runtime_data
    if coordinator.device.support_demand_control:
        async_add_entities([DaikinDemandControlSelect(coordinator)])


class DaikinDemandControlSelect(DaikinEntity, SelectEntity):
    """Select the demand control mode."""

    entity_description = DEMAND_CONTROL_MODE
    _attr_options = list(DAIKIN_DEMAND_CONTROL_OPTIONS)

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.mac}-demand_control"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the active demand control option."""
        return get_demand_control_option(self.device.get_demand_control())

    @override
    @daikin_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set the demand control mode."""
        await async_select_demand_control_option(self.coordinator, option)
