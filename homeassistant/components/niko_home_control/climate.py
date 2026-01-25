"""Support for Niko Home Control thermostats."""

from typing import Any

from nhc.const import THERMOSTAT_MODES, THERMOSTAT_MODES_REVERSE
from nhc.thermostat import NHCThermostat

from homeassistant.components.climate import (
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.sensor import UnitOfTemperature
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NikoHomeControlConfigEntry
from .const import (
    NIKO_HOME_CONTROL_THERMOSTAT_MODES_MAP,
    NikoHomeControlThermostatModes,
)
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Niko Home Control thermostat entry."""
    controller = entry.runtime_data

    async_add_entities(
        NikoHomeControlClimate(thermostat, controller, entry.entry_id)
        for thermostat in controller.thermostats.values()
    )


class NikoHomeControlClimate(NikoHomeControlEntity, ClimateEntity):
    """Representation of a Niko Home Control thermostat."""

    _attr_supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_name = None
    _action: NHCThermostat

    _attr_translation_key = "nhc_thermostat"

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.AUTO]

    _attr_preset_modes = [
        "day",
        "night",
        PRESET_ECO,
        "prog1",
        "prog2",
        "prog3",
    ]

    def _get_niko_mode(self, mode: str) -> int:
        """Return the Niko mode."""
        return THERMOSTAT_MODES_REVERSE.get(mode, NikoHomeControlThermostatModes.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            await self._action.set_temperature(kwargs.get(ATTR_TEMPERATURE))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._action.set_mode(self._get_niko_mode(preset_mode))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._action.set_mode(NIKO_HOME_CONTROL_THERMOSTAT_MODES_MAP[hvac_mode])

    async def async_turn_off(self) -> None:
        """Turn thermostat off."""
        await self._action.set_mode(NikoHomeControlThermostatModes.OFF)

    def update_state(self) -> None:
        """Update the state of the entity."""
        if self._action.state == NikoHomeControlThermostatModes.OFF:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_preset_mode = None
        elif self._action.state == NikoHomeControlThermostatModes.COOL:
            self._attr_hvac_mode = HVACMode.COOL
            self._attr_preset_mode = None
        else:
            self._attr_hvac_mode = HVACMode.AUTO
            self._attr_preset_mode = THERMOSTAT_MODES[self._action.state]

        self._attr_target_temperature = self._action.setpoint
        self._attr_current_temperature = self._action.measured
