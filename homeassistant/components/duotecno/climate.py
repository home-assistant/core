"""Support for Duotecno climate devices."""
from typing import Any

from duotecno.protocol import SensFanspeed, SensPreset
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DuotecnoClimate(channel) for channel in cntrl.get_units(["SensUnit"])
    )


class DuotecnoClimate(DuotecnoEntity, ClimateEntity):
    """Representation of a BinarySensor."""

    _unit: SensUnit
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
    _attr_preset_modes = list(SensPreset.__members__.keys())
    _attr_fan_modes = list(SensFanspeed.__members__.keys())

    @property
    def current_temperature(self) -> int | None:
        """Get the current temperature."""
        return self._unit.get_cur_temp()

    @property
    def target_temperature(self) -> float | None:
        """Get the target temperature."""
        return self._unit.get_target_temp()

    @property
    def hvac_mode(self) -> HVACMode:
        """Get the current hvac_mode."""
        state = self._unit.get_state()
        if state == 1:
            return HVACMode.HEAT
        if state == 2:
            return HVACMode.COOL
        return HVACMode.OFF

    @property
    def preset_mode(self) -> str:
        """Get the preset mode."""
        return SensPreset(self._unit.get_preset()).name

    @api_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._unit.set_temp(temp)

    @api_call
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        await self._unit.set_preset(SensPreset[preset_mode].value)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Duotecno does not support setting this, we can only display it."""
