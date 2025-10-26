"""Climate platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

import logging
from typing import Any

from pysaunum import MIN_TEMPERATURE

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
from .entity import LeilSaunaEntity
from .helpers import (
    convert_temperature,
    get_temperature_range_for_unit,
    get_temperature_unit,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


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
        min_temp, max_temp = get_temperature_range_for_unit(temp_unit)
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        temp_c = self.coordinator.data.current_temperature
        if temp_c is None:
            return None
        temp_unit = get_temperature_unit(self.hass)
        return convert_temperature(temp_c, UnitOfTemperature.CELSIUS, temp_unit)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        temp_c = self.coordinator.data.target_temperature
        if temp_c is None or temp_c < MIN_TEMPERATURE:
            return None
        temp_unit = get_temperature_unit(self.hass)
        return convert_temperature(temp_c, UnitOfTemperature.CELSIUS, temp_unit)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        session_active = self.coordinator.data.session_active
        return HVACMode.HEAT if session_active else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        session_active = self.coordinator.data.session_active
        if not session_active:
            return HVACAction.OFF

        heater_elements_active = self.coordinator.data.heater_elements_active
        return (
            HVACAction.HEATING
            if heater_elements_active and heater_elements_active > 0
            else HVACAction.IDLE
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_start_session()
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.async_stop_session()
        else:
            _LOGGER.warning("Unsupported HVAC mode: %s", hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Convert temperature to Celsius if needed
        temp_unit = get_temperature_unit(self.hass)
        temp_c = (
            convert_temperature(temperature, temp_unit, UnitOfTemperature.CELSIUS)
            or temperature
        )

        await self.coordinator.async_set_target_temperature(int(temp_c))
