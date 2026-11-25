"""Number entities for Daikin."""

from typing import override

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .demand_control import (
    async_set_demand_control_max_power,
    get_demand_control_max_power,
)
from .entity import DaikinEntity, daikin_exception_handler

DEMAND_CONTROL_MAX_POWER = NumberEntityDescription(
    key="demand_control_max_power",
    translation_key="demand_control_max_power",
    entity_category=EntityCategory.CONFIG,
    native_min_value=40,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin number entities."""
    coordinator = entry.runtime_data
    if coordinator.device.support_demand_control:
        async_add_entities([DaikinDemandControlNumber(coordinator)])


class DaikinDemandControlNumber(DaikinEntity, NumberEntity):
    """Set the manual demand control maximum power."""

    entity_description = DEMAND_CONTROL_MAX_POWER

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.mac}-demand_control_max_power"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the configured maximum power."""
        return get_demand_control_max_power(self.device.get_demand_control())

    @override
    @daikin_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set the manual maximum power."""
        await async_set_demand_control_max_power(self.coordinator, int(value))
