"""Water heater platform for MELCloud Home."""

from typing import Any, override

from aiomelcloudhome import ATWUnit

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import async_setup_unit_entities, perform_action
from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home water heaters."""
    coordinator = entry.runtime_data.coordinator

    async_setup_unit_entities(
        coordinator,
        async_add_entities,
        lambda _: (),  # Needed for the helper
        lambda units: (
            ATWWaterHeater(coordinator, unit)
            for unit in units
            if unit.capabilities and unit.capabilities.has_hot_water
        ),
    )


class ATWWaterHeater(MelCloudHomeATWUnitEntity, WaterHeaterEntity):
    """Representation of the hot water tank of a MELCloud Home ATW unit."""

    _attr_translation_key = "hot_water"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [STATE_HEAT_PUMP, STATE_HIGH_DEMAND]

    def __init__(self, coordinator: MelCloudHomeCoordinator, unit: ATWUnit) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self._attr_unique_id = f"{unit.id}_hot_water"

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the tank water temperature."""
        return self.unit.tank_water_temperature

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the target tank water temperature."""
        return self.unit.set_tank_water_temperature

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum target tank water temperature."""
        if (
            capabilities := self.unit.capabilities
        ) and capabilities.min_set_tank_temperature is not None:
            return capabilities.min_set_tank_temperature
        return super().min_temp

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum target tank water temperature."""
        if (
            capabilities := self.unit.capabilities
        ) and capabilities.max_set_tank_temperature is not None:
            return capabilities.max_set_tank_temperature
        return super().max_temp

    @property
    @override
    def target_temperature_step(self) -> float:
        """Return the target tank water temperature step."""
        if (capabilities := self.unit.capabilities) and capabilities.has_half_degrees:
            return 0.5
        return 1.0

    @property
    @override
    def current_operation(self) -> str:
        """Return the tank's operation, or off when the unit is off or in standby."""
        if not self.unit.power or self.unit.in_standby_mode:
            return STATE_OFF
        return STATE_HIGH_DEMAND if self.unit.forced_hot_water_mode else STATE_HEAT_PUMP

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target tank water temperature."""
        await perform_action(
            self.coordinator,
            self.coordinator.client.control_atw_unit(
                self._unit_id, set_tank_water_temperature=kwargs[ATTR_TEMPERATURE]
            ),
        )

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Turn forced hot water on or off."""
        await perform_action(
            self.coordinator,
            self.coordinator.client.control_atw_unit(
                self._unit_id,
                forced_hot_water_mode=operation_mode == STATE_HIGH_DEMAND,
            ),
        )
