"""Climate platform for AirPatrol integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirPatrolConfigEntry
from .coordinator import AirPatrolDataUpdateCoordinator
from .entity import AirPatrolEntity

PARALLEL_UPDATES = 0

AP_TO_HA_HVAC_MODES = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "off": HVACMode.OFF,
}
HA_TO_AP_HVAC_MODES = {value: key for key, value in AP_TO_HA_HVAC_MODES.items()}

AP_TO_HA_FAN_MODES = {
    "min": FAN_LOW,
    "max": FAN_HIGH,
    "auto": FAN_AUTO,
}
HA_TO_AP_FAN_MODES = {value: key for key, value in AP_TO_HA_FAN_MODES.items()}

AP_TO_HA_SWING_MODES = {
    "on": SWING_ON,
    "off": SWING_OFF,
}
HA_TO_AP_SWING_MODES = {value: key for key, value in AP_TO_HA_SWING_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirPatrolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirPatrol climate entities."""
    coordinator = config_entry.runtime_data
    units = coordinator.data

    async_add_entities(
        AirPatrolClimate(coordinator, unit_id)
        for unit_id, unit in units.items()
        if "climate" in unit
    )


class AirPatrolClimate(AirPatrolEntity, ClimateEntity):
    """AirPatrol climate entity."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    _attr_fan_modes = [FAN_LOW, FAN_HIGH, FAN_AUTO]
    _attr_swing_modes = [SWING_ON, SWING_OFF]
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0

    def __init__(
        self,
        coordinator: AirPatrolDataUpdateCoordinator,
        unit_id: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, unit_id)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-{unit_id}"

    @property
    def params(self) -> dict[str, Any]:
        """Return the current parameters for the climate entity."""
        return self.climate_data.get("ParametersData") or {}

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        if humidity := self.climate_data.get("RoomHumidity"):
            return float(humidity)
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if temp := self.climate_data.get("RoomTemp"):
            return float(temp)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if temp := self.params.get("PumpTemp"):
            return float(temp)
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        pump_power = self.params.get("PumpPower")
        pump_mode = self.params.get("PumpMode")

        if pump_power and pump_power == "on" and pump_mode:
            return AP_TO_HA_HVAC_MODES.get(pump_mode)
        return HVACMode.OFF

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_speed = self.params.get("FanSpeed")
        if fan_speed:
            return AP_TO_HA_FAN_MODES.get(fan_speed)
        return None

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        swing = self.params.get("Swing")
        if swing:
            return AP_TO_HA_SWING_MODES.get(swing)
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        params = self.params.copy()

        if ATTR_TEMPERATURE in kwargs:
            temp = kwargs[ATTR_TEMPERATURE]
            params["PumpTemp"] = f"{temp:.3f}"

        await self._async_set_params(params)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        params = self.params.copy()

        if hvac_mode == HVACMode.OFF:
            params["PumpPower"] = "off"
        else:
            params["PumpPower"] = "on"
            params["PumpMode"] = HA_TO_AP_HVAC_MODES.get(hvac_mode)

        await self._async_set_params(params)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        params = self.params.copy()
        params["FanSpeed"] = HA_TO_AP_FAN_MODES.get(fan_mode)

        await self._async_set_params(params)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        params = self.params.copy()
        params["Swing"] = HA_TO_AP_SWING_MODES.get(swing_mode)

        await self._async_set_params(params)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        params = self.params.copy()
        if mode := AP_TO_HA_HVAC_MODES.get(params["PumpMode"]):
            await self.async_set_hvac_mode(mode)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _async_set_params(self, params: dict[str, Any]) -> None:
        """Set the unit to dry mode."""
        new_climate_data = self.climate_data.copy()
        new_climate_data["ParametersData"] = params

        await self.coordinator.api.set_unit_climate_data(
            self._unit_id, new_climate_data
        )

        await self.coordinator.async_request_refresh()
