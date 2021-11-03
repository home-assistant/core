"""Support for Velbus thermostat."""
from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import VelbusEntity
from .const import DOMAIN, PRESET_MODES


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("climate"):
        entities.append(VelbusClimate(channel))
    async_add_entities(entities)


class VelbusClimate(VelbusEntity, ClimateEntity):
    """Representation of a Velbus thermostat."""

    @property
    def supported_features(self) -> int:
        """Return the list off supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def temperature_unit(self) -> str:
        """Return the unit."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> int | None:
        """Return the current temperature."""
        return self._channel.get_state()

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature we try to reach."""
        return self._channel.get_climate_target()

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of all possible presets."""
        return list(PRESET_MODES)

    @property
    def preset_mode(self) -> str | None:
        """Return the current Preset for this channel."""
        return next(
            (
                key
                for key, val in PRESET_MODES.items()
                if val == self._channel.get_climate_preset()
            ),
            None,
        )

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._channel.set_temp(temp)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the new preset mode."""
        await self._channel.set_preset(PRESET_MODES[preset_mode])
        self.async_write_ha_state()
