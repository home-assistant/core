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
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PRESET_MODES
from .entity import VelbusEntity, api_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    async_add_entities(VelbusClimate(channel) for channel in cntrl.get_all("climate"))


class VelbusClimate(VelbusEntity, ClimateEntity):
    """Representation of a Velbus thermostat."""

    _channel: VelbusTemp
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL]
    _attr_preset_modes = list(PRESET_MODES)
    _enable_turn_on_off_backwards_compatibility = False

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

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current hvac mode based on cool_mode message."""
        return HVACMode.COOL if self._channel.get_cool_mode() else HVACMode.HEAT

    @api_call
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._channel.set_temp(temp)
        self.async_write_ha_state()

    @api_call
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the new preset mode."""
        await self._channel.set_preset(PRESET_MODES[preset_mode])
        self.async_write_ha_state()

    @api_call
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the new hvac mode."""
        if hvac_mode not in self._attr_hvac_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_hvac_mode",
                translation_placeholders={"hvac_mode": str(hvac_mode)},
            )
        await self._channel.set_mode(hvac_mode)
        self.async_write_ha_state()
