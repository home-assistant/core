"""Climate platform — one entity per space-heating circuit (RK1-3)."""

from typing import Any

from trovis_modbus import HeatingCircuit, OperatingMode

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity

_TO_HVAC = {
    OperatingMode.STANDBY: HVACMode.OFF,
    OperatingMode.AUTOMATIC: HVACMode.AUTO,
    OperatingMode.PROGRAM: HVACMode.AUTO,
    OperatingMode.DAY: HVACMode.HEAT,
    OperatingMode.NIGHT: HVACMode.HEAT,
    OperatingMode.MANUAL: HVACMode.HEAT,
}
_FROM_HVAC = {
    HVACMode.OFF: OperatingMode.STANDBY,
    HVACMode.AUTO: OperatingMode.AUTOMATIC,
    HVACMode.HEAT: OperatingMode.DAY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a climate entity per heating circuit."""
    coordinator = entry.runtime_data
    async_add_entities(
        TrovisHeatingCircuitClimate(coordinator, index) for index in (1, 2, 3)
    )


class TrovisHeatingCircuitClimate(TrovisEntity, ClimateEntity):
    """A heating circuit as a thermostat (room setpoint + mode)."""

    _attr_name = None  # primary entity -> takes the sub-device's name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: TrovisCoordinator, index: int) -> None:
        """Initialize the heating-circuit climate entity."""
        super().__init__(
            coordinator,
            key=f"climate_circuit_{index}",
            component=f"heating_circuit_{index}",
        )

    @property
    def _circuit(self) -> HeatingCircuit:
        return self._subsystem  # type: ignore[return-value]

    @property
    def current_temperature(self) -> float | None:
        """Return the room temperature."""
        return self._circuit.room_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the active room setpoint."""
        return self._circuit.room_setpoint_active

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        mode = self._circuit.mode
        return _TO_HVAC.get(mode) if mode is not None else None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        if self._circuit.mode is OperatingMode.STANDBY:
            return HVACAction.OFF
        if self._circuit.pump_running is None:
            return None
        return HVACAction.HEATING if self._circuit.pump_running else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._circuit.set_room_setpoint_day(temperature)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new HVAC mode."""
        await self._circuit.set_mode(_FROM_HVAC[hvac_mode])
        await self.coordinator.async_request_refresh()
