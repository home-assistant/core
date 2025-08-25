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

# HVAC modes supported by AirPatrol
HVAC_MODES = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "off": HVACMode.OFF,
}

# Fan speeds supported by AirPatrol
FAN_MODES = {
    "min": FAN_LOW,
    "max": FAN_HIGH,
    "auto": FAN_AUTO,
}

# Swing modes supported by AirPatrol
SWING_MODES = {
    "on": SWING_ON,
    "off": SWING_OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirPatrolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirPatrol climate entities."""
    coordinator = config_entry.runtime_data
    # Create climate entities for each unit
    units = coordinator.data or []

    async_add_entities(
        [
            AirPatrolClimate(coordinator, unit, unit["unit_id"])
            for unit in units
            if "climate" in unit
        ]
    )


class AirPatrolClimate(AirPatrolEntity, ClimateEntity):
    """AirPatrol climate entity."""

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
        unit: dict[str, Any],
        unit_id: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, unit, unit_id)
        unique_id = getattr(coordinator.config_entry, "unique_id", None)
        self._attr_unique_id = (
            f"{unique_id}_{unit_id}_climate"
            if unique_id is not None
            else f"{unit_id}_climate"
        )
        self._attr_translation_key = "climate"
        self._unavailable_logged = False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        is_available = super().available and "climate" in self._unit
        if not is_available and not self._unavailable_logged:
            self._unavailable_logged = True
        elif self._unavailable_logged:
            self._unavailable_logged = False
        return is_available

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        climate_data = self._unit.get("climate", {})
        if humidity := climate_data.get("RoomHumidity"):
            return float(humidity)
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        climate_data = self._unit.get("climate", {})
        if temp := climate_data.get("RoomTemp"):
            return float(temp)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {})
        if temp := params.get("PumpTemp"):
            return float(temp)
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {})
        pump_power = params.get("PumpPower", "off")
        pump_mode = params.get("PumpMode", "heat")

        if pump_power == "off":
            return HVACMode.OFF
        return HVAC_MODES.get(pump_mode, HVACMode.HEAT)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {})
        fan_speed = params.get("FanSpeed", "max")
        return FAN_MODES.get(fan_speed, FAN_HIGH)

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {})
        swing = params.get("Swing", "off")
        return SWING_MODES.get(swing, SWING_OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        params = self.params().copy()

        if ATTR_TEMPERATURE in kwargs:
            # Convert temperature to AirPatrol format (string with 3 decimal places)
            temp = kwargs[ATTR_TEMPERATURE]
            params["PumpTemp"] = f"{temp:.3f}"

        # Update the climate data
        await self._async_set_params(params)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        params = self.params().copy()

        if hvac_mode == HVACMode.OFF:
            params["PumpPower"] = "off"
        else:
            params["PumpPower"] = "on"
            # Map HVAC mode to pump mode
            if hvac_mode == HVACMode.HEAT:
                params["PumpMode"] = "heat"
            elif hvac_mode == HVACMode.COOL:
                params["PumpMode"] = "cool"

        # Update the climate data
        await self._async_set_params(params)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        params = self.params().copy()

        # Map fan mode to AirPatrol fan speed
        if fan_mode == FAN_LOW:
            params["FanSpeed"] = "min"
        elif fan_mode == FAN_HIGH:
            params["FanSpeed"] = "max"
        elif fan_mode == FAN_AUTO:
            params["FanSpeed"] = "auto"

        # Update the climate data
        await self._async_set_params(params)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        params = self.params().copy()

        # Map swing mode to AirPatrol swing setting
        if swing_mode in [SWING_ON, SWING_OFF]:
            params["Swing"] = swing_mode

        # Update the climate data
        await self._async_set_params(params)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _async_set_params(self, params: dict[str, Any]) -> None:
        """Set the unit to dry mode."""
        new_climate_data = self.climate_data().copy()
        new_climate_data["ParametersData"] = params

        response_data = await self.coordinator.api.set_unit_climate_data(
            self._unit_id, new_climate_data
        )
        # Update local data with the response data
        self._unit["climate"] = response_data
        self.async_write_ha_state()

    def params(self) -> dict[str, Any]:
        """Return the current parameters for the climate entity."""
        return self.climate_data().get("ParametersData", {})

    def climate_data(self) -> dict[str, Any]:
        """Return the current climate data for the entity."""
        return self._unit.get("climate", {})
