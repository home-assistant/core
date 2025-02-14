"""Support for Niko Home Control thermostats."""

from typing import Any

from nhc.const import THERMOSTAT_MODES
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NikoHomeControlConfigEntry
from .const import NIKO_THERMOSTAT_MODES_MAP
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_name = None
    _action: NHCThermostat

    _attr_translation_key = "nhc_thermostat"

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.AUTO]

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return [
            "day",
            "night",
            PRESET_ECO,
            "prog1",
            "prog2",
            "prog3",
        ]

    def _get_niko_mode(self, mode: str) -> int:
        """Return the Niko mode."""
        for key, value in THERMOSTAT_MODES.items():
            if value == mode:
                return key
        return 3

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._action.set_temperature(kwargs.get(ATTR_TEMPERATURE, 20) * 10)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._action.set_mode(self._get_niko_mode(preset_mode))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._action.set_mode(NIKO_THERMOSTAT_MODES_MAP.get(hvac_mode))

    def update_state(self) -> None:
        """Update the state of the entity."""
        if self._action.state = NIKO_THERMOSTAT_MODES_MAP.off:
            self._attr_hvac_mode = HVACMode.OFF
        elif self._action.state == NIKO_THERMOSTAT_MODES_MAP.cool:
            self._attr_hvac_mode = HVACMode.COOL
        else:
            self._attr_hvac_mode = HVACMode.AUTO
            self._attr_preset_mode = THERMOSTAT_MODES[self._action.state]

        self._attr_target_temperature = self._action.setpoint / 10
        self._attr_current_temperature = self._action.measured / 10
