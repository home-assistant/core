"""Support for Duotecno climate devices."""

from __future__ import annotations

from typing import Any, Final

from duotecno.controller import PyDuotecno
from duotecno.unit import SensUnit

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import DuotecnoEntity, api_call

HVACMODE: Final = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
}
HVACMODE_REVERSE: Final = {value: key for key, value in HVACMODE.items()}

PRESETMODES: Final = {"sun": 0, "half_sun": 1, "moon": 2, "half_moon": 3}
PRESETMODES_REVERSE: Final = {value: key for key, value in PRESETMODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Duotecno climate based on config_entry."""
    cntrl: PyDuotecno = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DuotecnoClimate(channel) for channel in cntrl.get_units(["SensUnit"])
    )


class DuotecnoClimate(DuotecnoEntity, ClimateEntity):
    """Representation of a Duotecno climate entity."""

    _unit: SensUnit
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = list(HVACMODE_REVERSE)
    _attr_preset_modes = list(PRESETMODES)
    _attr_translation_key = "duotecno"
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def current_temperature(self) -> float | None:
        """Get the current temperature."""
        return self._unit.get_cur_temp()

    @property
    def target_temperature(self) -> float | None:
        """Get the target temperature."""
        return self._unit.get_target_temp()

    @property
    def hvac_mode(self) -> HVACMode:
        """Get the current hvac_mode."""
        return HVACMODE[self._unit.get_state()]

    @property
    def preset_mode(self) -> str:
        """Get the preset mode."""
        return PRESETMODES_REVERSE[self._unit.get_preset()]

    @api_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._unit.set_temp(temp)

    @api_call
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        await self._unit.set_preset(PRESETMODES[preset_mode])

    @api_call
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Duotecno does not support setting this, we can only display it."""
        if hvac_mode == HVACMode.OFF:
            await self._unit.turn_off()
        else:
            await self._unit.turn_on()
