"""Support for Velbus thermostat."""
from __future__ import annotations

from typing import Any

from velbusaio.channels import Temperature as VelbusTemp

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VelbusEntity
from .const import DOMAIN, PRESET_MODES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("climate"):
        entities.append(VelbusClimate(channel))
    async_add_entities(entities)


class VelbusClimate(VelbusEntity, ClimateEntity):
    """Representation of a Velbus thermostat."""

    _channel: VelbusTemp
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_preset_modes = list(PRESET_MODES)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._channel.get_climate_target()

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

    @property
    def current_temperature(self) -> int | None:
        """Return the current temperature."""
        return self._channel.get_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._channel.set_temp(temp)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the new preset mode."""
        await self._channel.set_preset(PRESET_MODES[preset_mode])
        self.async_write_ha_state()
