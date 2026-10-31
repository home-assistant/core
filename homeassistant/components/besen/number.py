"""Number platform for Besen."""

from typing import override

from besen.const import FALLBACK_MAX_CHARGE_AMPS, MIN_CHARGE_AMPS

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenConfigEntry
from .coordinator import BesenCoordinator
from .entity import BesenEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Besen number platform."""

    async_add_entities([BesenChargingCurrentNumber(entry.runtime_data)])


class BesenChargingCurrentNumber(BesenEntity, NumberEntity):
    """Charging current control."""

    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_CHARGE_AMPS
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator: BesenCoordinator) -> None:
        """Initialize the charging current control."""

        super().__init__(coordinator, "charging_current")

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum charging current."""

        return self.coordinator.data.info.output_max_amps or FALLBACK_MAX_CHARGE_AMPS

    @property
    @override
    def native_value(self) -> float | None:
        """Return the configured charging current."""

        return self.coordinator.data.config.charge_amps

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the charging current."""

        await self.coordinator.async_set_charge_amps(int(value))
