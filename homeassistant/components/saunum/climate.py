"""Climate platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .const import MIN_TEMPERATURE_C, REG_SESSION_ACTIVE, REG_TARGET_TEMPERATURE
from .entity import LeilSaunaEntity
from .helpers import (
    convert_temperature,
    get_temperature_range_for_unit,
    get_temperature_unit,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna climate entity."""
    coordinator = entry.runtime_data
    async_add_entities([LeilSaunaClimate(coordinator)])


class LeilSaunaClimate(LeilSaunaEntity, ClimateEntity):
    """Representation of a Saunum Leil Sauna climate entity."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator: LeilSaunaCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, "climate")

        # Set temperature unit and range
        temp_unit = get_temperature_unit(coordinator.hass)
        self._attr_temperature_unit = temp_unit
        min_temp, max_temp, _default_temp = get_temperature_range_for_unit(temp_unit)
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp

        # Optimistic state for responsive UI
        self._optimistic_hvac_mode: HVACMode | None = None
        self._optimistic_target_temp: float | None = None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        temp_c = self.coordinator.data.get("current_temperature")
        if temp_c is None:
            return None
        temp_unit = get_temperature_unit(self.hass)
        return convert_temperature(temp_c, UnitOfTemperature.CELSIUS, temp_unit)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        # Use optimistic state if available
        if self._optimistic_target_temp is not None:
            return self._optimistic_target_temp

        temp_c = self.coordinator.data.get("target_temperature")
        if temp_c is None or temp_c < MIN_TEMPERATURE_C:
            return None
        temp_unit = get_temperature_unit(self.hass)
        return convert_temperature(temp_c, UnitOfTemperature.CELSIUS, temp_unit)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Use optimistic state if available
        if self._optimistic_hvac_mode is not None:
            return self._optimistic_hvac_mode

        session_active = self.coordinator.data.get("session_active", 0)
        return HVACMode.HEAT if session_active else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        session_active = self.coordinator.data.get("session_active", 0)
        if not session_active:
            return HVACAction.OFF

        heater_status = self.coordinator.data.get("heater_status", 0)
        return HVACAction.HEATING if heater_status else HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            # Set optimistic state immediately for responsive UI
            self._optimistic_hvac_mode = HVACMode.HEAT
            self.async_write_ha_state()

            success = await self.coordinator.async_write_register(REG_SESSION_ACTIVE, 1)

            # Clear optimistic state after coordinator refresh
            self._optimistic_hvac_mode = None
            if not success:
                # If write failed, trigger state update to revert to actual state
                self.async_write_ha_state()
        elif hvac_mode == HVACMode.OFF:
            # Set optimistic state immediately for responsive UI
            self._optimistic_hvac_mode = HVACMode.OFF
            self.async_write_ha_state()

            success = await self.coordinator.async_write_register(REG_SESSION_ACTIVE, 0)

            # Clear optimistic state after coordinator refresh
            self._optimistic_hvac_mode = None
            if not success:
                # If write failed, trigger state update to revert to actual state
                self.async_write_ha_state()
        else:
            _LOGGER.warning("Unsupported HVAC mode: %s", hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Set optimistic state immediately for responsive UI
        self._optimistic_target_temp = temperature
        self.async_write_ha_state()

        # Convert temperature to Celsius if needed
        temp_unit = get_temperature_unit(self.hass)
        temp_c = (
            convert_temperature(temperature, temp_unit, UnitOfTemperature.CELSIUS)
            or temperature
        )

        success = await self.coordinator.async_write_register(
            REG_TARGET_TEMPERATURE, int(temp_c)
        )

        # Clear optimistic state after coordinator refresh
        self._optimistic_target_temp = None
        if not success:
            # If write failed, trigger state update to revert to actual state
            self.async_write_ha_state()
