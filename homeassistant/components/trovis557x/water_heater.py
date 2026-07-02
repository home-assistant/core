"""Water heater platform — the domestic hot water circuit (HK4)."""

from typing import Any

from trovis_modbus import HotWater, OperatingMode

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity

# Operation-list labels <-> controller modes.
_MODES = {
    "auto": OperatingMode.AUTOMATIC,
    "on": OperatingMode.DAY,
    "off": OperatingMode.STANDBY,
}
_REVERSE = {mode: label for label, mode in _MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hot water entity."""
    async_add_entities([TrovisHotWaterEntity(entry.runtime_data)])


class TrovisHotWaterEntity(TrovisEntity, WaterHeaterEntity):
    """Domestic hot water as a water heater."""

    _attr_name = None  # primary entity -> takes the sub-device's name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = list(_MODES)

    def __init__(self, coordinator: TrovisCoordinator) -> None:
        """Initialize the hot water entity."""
        super().__init__(coordinator, key="water_heater", component="hot_water")

    @property
    def _hot_water(self) -> HotWater:
        return self._subsystem  # type: ignore[return-value]

    @property
    def current_temperature(self) -> float | None:
        """Return the storage temperature."""
        return self._hot_water.storage_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the active setpoint."""
        return self._hot_water.setpoint_active

    @property
    def min_temp(self) -> float:
        """Return the minimum settable temperature."""
        return self._hot_water.setpoint_min or 20.0

    @property
    def max_temp(self) -> float:
        """Return the maximum settable temperature."""
        return self._hot_water.setpoint_max or 90.0

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode label."""
        return _REVERSE.get(self._hot_water.mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._hot_water.set_setpoint(temperature)
            await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set a new operation mode."""
        await self._hot_water.set_mode(_MODES[operation_mode])
        await self.coordinator.async_request_refresh()
