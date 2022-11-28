"""Support for Balboa Spa Wifi adaptor."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CLIMATE, CLIMATE_SUPPORTED_FANSTATES, CLIMATE_SUPPORTED_MODES, DOMAIN
from .entity import BalboaEntity

SET_TEMPERATURE_WAIT = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa climate device."""
    async_add_entities(
        [
            BalboaSpaClimate(
                entry,
                hass.data[DOMAIN][entry.entry_id],
                CLIMATE,
            )
        ],
    )


class BalboaSpaClimate(BalboaEntity, ClimateEntity):
    """Representation of a Balboa Spa Climate device."""

    _attr_icon = "mdi:hot-tub"
    _attr_fan_modes = CLIMATE_SUPPORTED_FANSTATES
    _attr_hvac_modes = CLIMATE_SUPPORTED_MODES

    def __init__(self, entry, client, devtype, num=None):
        """Initialize the climate entity."""
        super().__init__(entry, client, devtype, num)
        self._balboa_to_ha_blower_map = {
            self._client.BLOWER_OFF: FAN_OFF,
            self._client.BLOWER_LOW: FAN_LOW,
            self._client.BLOWER_MEDIUM: FAN_MEDIUM,
            self._client.BLOWER_HIGH: FAN_HIGH,
        }
        self._ha_to_balboa_blower_map = {
            value: key for key, value in self._balboa_to_ha_blower_map.items()
        }
        self._balboa_to_ha_heatmode_map = {
            self._client.HEATMODE_READY: HVACMode.HEAT,
            self._client.HEATMODE_RNR: HVACMode.AUTO,
            self._client.HEATMODE_REST: HVACMode.OFF,
        }
        self._ha_heatmode_to_balboa_map = {
            value: key for key, value in self._balboa_to_ha_heatmode_map.items()
        }
        scale = self._client.get_tempscale()
        self._attr_preset_modes = self._client.get_heatmode_stringlist()
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )
        if self._client.have_blower():
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        self._attr_min_temp = self._client.tmin[self._client.TEMPRANGE_LOW][scale]
        self._attr_max_temp = self._client.tmax[self._client.TEMPRANGE_HIGH][scale]
        self._attr_temperature_unit = TEMP_FAHRENHEIT
        self._attr_precision = PRECISION_WHOLE
        if self._client.get_tempscale() == self._client.TSCALE_C:
            self._attr_temperature_unit = TEMP_CELSIUS
            self._attr_precision = PRECISION_HALVES

    @property
    def hvac_mode(self) -> str:
        """Return the current HVAC mode."""
        mode = self._client.get_heatmode()
        return self._balboa_to_ha_heatmode_map[mode]

    @property
    def hvac_action(self) -> str:
        """Return the current operation mode."""
        if self._client.get_heatstate() >= self._client.ON:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        fanmode = self._client.get_blower()
        return self._balboa_to_ha_blower_map.get(fanmode, FAN_OFF)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.get_curtemp()

    @property
    def target_temperature(self):
        """Return the target temperature we try to reach."""
        return self._client.get_settemp()

    @property
    def preset_mode(self):
        """Return current preset mode."""
        return self._client.get_heatmode(True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        scale = self._client.get_tempscale()
        newtemp = kwargs[ATTR_TEMPERATURE]
        if newtemp > self._client.tmax[self._client.TEMPRANGE_LOW][scale]:
            await self._client.change_temprange(self._client.TEMPRANGE_HIGH)
            await asyncio.sleep(SET_TEMPERATURE_WAIT)
        if newtemp < self._client.tmin[self._client.TEMPRANGE_HIGH][scale]:
            await self._client.change_temprange(self._client.TEMPRANGE_LOW)
            await asyncio.sleep(SET_TEMPERATURE_WAIT)
        await self._client.send_temp_change(newtemp)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        modelist = self._client.get_heatmode_stringlist()
        self._async_validate_mode_or_raise(preset_mode)
        if preset_mode not in modelist:
            raise ValueError(f"{preset_mode} is not a valid preset mode")
        await self._client.change_heatmode(modelist.index(preset_mode))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        await self._client.change_blower(self._ha_to_balboa_blower_map[fan_mode])

    def _async_validate_mode_or_raise(self, mode):
        """Check that the mode can be set."""
        if mode == self._client.HEATMODE_RNR:
            raise ValueError(f"{mode} can only be reported but not set")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode.

        OFF = Rest
        AUTO = Ready in Rest (can't be set, only reported)
        HEAT = Ready
        """
        mode = self._ha_heatmode_to_balboa_map[hvac_mode]
        self._async_validate_mode_or_raise(mode)
        await self._client.change_heatmode(self._ha_heatmode_to_balboa_map[hvac_mode])
