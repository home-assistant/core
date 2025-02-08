"""Thermostat platform Niko Home Control."""

from __future__ import annotations

from typing import Any

from nhc.thermostat import NHCThermostat

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NikoHomeControlConfigEntry
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Niko Home Control thermostat entry."""
    controller = entry.runtime_data

    async_add_entities(
        NikoHomeControlThermostat(thermostat, controller, entry.entry_id)
        for thermostat in controller.thermostats.values()
    )


class NikoHomeControlThermostat(NikoHomeControlEntity, ClimateEntity):
    """Representation of a Niko Thermostat."""

    _attr_name = None
    _action: NHCThermostat
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
    ]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            newMode = 0
        elif hvac_mode == HVACMode.OFF:
            newMode = 3
        elif hvac_mode == HVACMode.COOL:
            newMode = 4
        elif hvac_mode == HVACMode.AUTO:
            newMode = 5
        else:
            newMode = 5

        await self._action.set_mode(newMode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE, 20)
        self._attr_target_temperature = int(temperature * 10)
        newTemp = int(temperature * 10)
        await self._action.set_temperature(newTemp)

    def update_state(self) -> None:
        """Update the state of the thermostat."""
        # print("update_state", self._action.measured)
        self._attr_current_temperature = self._action.measured / 10
        self._attr_target_temperature = self._action.setpoint / 10

        # _action.mode
        # 0 is day
        # 1 is night
        # 2 is eco
        # 3 is off
        # 4 is cool
        # 5 is prog1
        # 6 is prog2
        # 7 is prog3

        if self._action.mode in (0, 1, 2):
            self._attr_hvac_mode = HVACMode.HEAT
        elif self._action.mode == 3:
            self._attr_hvac_mode = HVACMode.OFF
        elif self._action.mode == 4:
            self._attr_hvac_mode = HVACMode.COOL
        elif self._action.mode in (5, 6, 7):
            self._attr_hvac_mode = HVACMode.AUTO
        else:
            self._attr_hvac_mode = HVACMode.AUTO
