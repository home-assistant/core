"""Climate platform for AirPatrol integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirPatrolDataUpdateCoordinator

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# HVAC modes supported by AirPatrol
HVAC_MODES = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "off": HVACMode.OFF,
}

# Fan speeds supported by AirPatrol
FAN_MODES = {
    "min": FAN_LOW,
    "med": FAN_MEDIUM,
    "max": FAN_HIGH,
}

# Swing modes supported by AirPatrol
SWING_MODES = {
    "on": SWING_ON,
    "off": SWING_OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirPatrol climate entities."""
    coordinator: AirPatrolDataUpdateCoordinator = config_entry.runtime_data
    # Create climate entities for each unit
    entities = []
    units = await coordinator.api.get_data()
    entities = [
        AirPatrolClimate(coordinator, unit, unit["unit_id"])
        for unit in units
        if "climate" in unit
    ]

    async_add_entities(entities)


class AirPatrolClimate(
    CoordinatorEntity[AirPatrolDataUpdateCoordinator], ClimateEntity
):
    """AirPatrol climate entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(
        self,
        coordinator: AirPatrolDataUpdateCoordinator,
        unit: dict[str, Any],
        unit_id: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._unit = unit
        self._unit_id = unit_id
        unique_id = getattr(coordinator.config_entry, "unique_id", None)
        self._attr_unique_id = (
            f"{unique_id}_{unit_id}_climate"
            if unique_id is not None
            else f"{unit_id}_climate"
        )
        self._attr_translation_key = "climate"
        self._unavailable_logged = False
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit_id)},
            name=unit["name"],
            manufacturer=unit["manufacturer"],
            model=unit["model"],
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        is_available = (
            super().available
            and self.coordinator.data is not None
            and any(
                isinstance(u, dict) and u.get("unit_id") == self._unit_id
                for u in self.coordinator.data
            )
            and "climate" in self._unit
        )
        if not is_available and not self._unavailable_logged:
            _LOGGER.info("The climate entity '%s' is unavailable", self._attr_unique_id)
            self._unavailable_logged = True
        elif self._unavailable_logged:
            _LOGGER.info("The climate entity '%s' is back online", self._attr_unique_id)
            self._unavailable_logged = False
        return is_available

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        climate_data = self._unit.get("climate", {})
        if humidity := climate_data.get("RoomHumidity"):
            try:
                return float(humidity)
            except (ValueError, TypeError):
                _LOGGER.error("Failed to convert humidity to float: %s", humidity)
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        climate_data = self._unit.get("climate", {})
        if temp := climate_data.get("RoomTemp"):
            try:
                return float(temp)
            except (ValueError, TypeError):
                _LOGGER.error("Failed to convert temperature to float: %s", temp)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {})
        if temp := params.get("PumpTemp"):
            try:
                return float(temp)
            except (ValueError, TypeError):
                _LOGGER.error("Failed to convert temperature to float: %s", temp)
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
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {})
        pump_power = params.get("PumpPower", "off")
        pump_mode = params.get("PumpMode", "heat")

        if pump_power == "off":
            return HVACAction.OFF

        if pump_mode == "heat":
            return HVACAction.HEATING
        if pump_mode == "cool":
            return HVACAction.COOLING
        return HVACAction.IDLE

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

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return [FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def swing_modes(self) -> list[str]:
        """Return the list of available swing modes."""
        return [SWING_ON, SWING_OFF]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 16.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30.0

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {}).copy()

        if ATTR_TEMPERATURE in kwargs:
            # Convert temperature to AirPatrol format (string with 3 decimal places)
            temp = kwargs[ATTR_TEMPERATURE]
            params["PumpTemp"] = f"{temp:.3f}"

        # Update the climate data
        new_climate_data = climate_data.copy()
        new_climate_data["ParametersData"] = params

        response_data = await self.coordinator.api.set_unit_climate_data(
            self._unit_id, new_climate_data
        )
        # Update local data with the response data
        self._unit["climate"] = response_data
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {}).copy()

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
        new_climate_data = climate_data.copy()
        new_climate_data["ParametersData"] = params

        response_data = await self.coordinator.api.set_unit_climate_data(
            self._unit_id, new_climate_data
        )
        # Update local data with the response data
        self._unit["climate"] = response_data
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {}).copy()

        # Map fan mode to AirPatrol fan speed
        if fan_mode == FAN_LOW:
            params["FanSpeed"] = "min"
        elif fan_mode == FAN_MEDIUM:
            params["FanSpeed"] = "med"
        elif fan_mode == FAN_HIGH:
            params["FanSpeed"] = "max"

        # Update the climate data
        new_climate_data = climate_data.copy()
        new_climate_data["ParametersData"] = params

        response_data = await self.coordinator.api.set_unit_climate_data(
            self._unit_id, new_climate_data
        )
        # Update local data with the response data
        self._unit["climate"] = response_data
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        climate_data = self._unit.get("climate", {})
        params = climate_data.get("ParametersData", {}).copy()

        # Map swing mode to AirPatrol swing setting
        if swing_mode == SWING_ON:
            params["Swing"] = "auto"
        elif swing_mode == SWING_OFF:
            params["Swing"] = "off"

        # Update the climate data
        new_climate_data = climate_data.copy()
        new_climate_data["ParametersData"] = params

        response_data = await self.coordinator.api.set_unit_climate_data(
            self._unit_id, new_climate_data
        )
        # Update local data with the response data
        self._unit["climate"] = response_data
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
