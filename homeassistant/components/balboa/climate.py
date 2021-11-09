"""Support for Balboa Spa Wifi adaptor."""
from __future__ import annotations

import math

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from .balboa_entity import BalboaEntity
from .const import CLIMATE, CLIMATE_SUPPORTED_FANSTATES, CLIMATE_SUPPORTED_MODES


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the spa climate device."""
    async_add_entities([BalboaSpaClimate(hass, entry, CLIMATE)], True)


class BalboaSpaClimate(BalboaEntity, ClimateEntity):
    """Representation of a Balboa Spa Climate device."""

    _attr_icon = "mdi:hot-tub"
    _attr_fan_modes = CLIMATE_SUPPORTED_FANSTATES

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

        if self._client.have_blower():
            features |= SUPPORT_FAN_MODE

        return features

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of supported HVAC modes."""
        if self._client.get_heatmode() == self._client.HEATMODE_RNR:
            return [*CLIMATE_SUPPORTED_MODES, HVAC_MODE_AUTO]
        return CLIMATE_SUPPORTED_MODES

    @property
    def hvac_mode(self) -> str:
        """Return the current HVAC mode."""
        mode = self._client.get_heatmode()
        if mode == self._client.HEATMODE_READY:
            return HVAC_MODE_HEAT
        if mode == self._client.HEATMODE_RNR:
            return HVAC_MODE_AUTO
        return HVAC_MODE_OFF

    @property
    def hvac_action(self) -> str:
        """Return the current operation mode."""
        state = self._client.get_heatstate()
        if state >= self._client.ON:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        fanmode = self._client.get_blower()
        if fanmode is None:
            return FAN_OFF
        if fanmode == self._client.BLOWER_OFF:
            return FAN_OFF
        if fanmode == self._client.BLOWER_LOW:
            return FAN_LOW
        if fanmode == self._client.BLOWER_MEDIUM:
            return FAN_MEDIUM
        if fanmode == self._client.BLOWER_HIGH:
            return FAN_HIGH
        return FAN_OFF

    @property
    def precision(self) -> float:
        """Return the precision of the system.

        Balboa spas return data in C or F depending on how the display is set,
        because ultimately, we are just reading the display.
        In C, we have half-degree accuracy, in F, whole degree.
        """
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement, as defined by the API."""
        tscale = self._client.get_tempscale()
        if tscale == self._client.TSCALE_C:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.get_curtemp()

    @property
    def target_temperature(self):
        """Return the target temperature we try to reach."""
        return self._client.get_settemp()

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature supported by the spa."""
        trange = self._client.get_temprange()
        scale = self._client.get_tempscale()
        return self._client.tmin[trange][scale]

    @property
    def max_temp(self) -> int:
        """Return the minimum temperature supported by the spa."""
        trange = self._client.get_temprange()
        scale = self._client.get_tempscale()
        return self._client.tmax[trange][scale]

    @property
    def preset_modes(self):
        """Return the valid preset modes."""
        modes = [
            mode
            for mode in self._client.get_heatmode_stringlist()
            # only return "Ready in Rest" as an option if the spa is currently in that
            # mode since it is a status rather than an available mode to be selected
            if self._client.get_heatmode() == self._client.HEATMODE_RNR
            or mode != self._client.get_heatmode_stringlist()[self._client.HEATMODE_RNR]
        ]
        return modes

    @property
    def preset_mode(self):
        """Return current preset mode."""
        return self._client.get_heatmode(True)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "time": f"{self._client.time_hour:02d}:{self._client.time_minute:02d}",
        }

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        spa_unit = self._client.get_tempscale()
        if spa_unit != self.get_temp_unit():
            if spa_unit == self._client.TSCALE_F:
                temperature = math.floor(temperature + 0.5)
            else:
                temperature = 0.5 * round(temperature / 0.5)
        await self._client.send_temp_change(temperature)

    async def async_set_preset_mode(self, preset_mode) -> None:
        """Set new preset mode."""
        modelist = self._client.get_heatmode_stringlist()
        if preset_mode in modelist:
            await self._client.change_heatmode(modelist.index(preset_mode))

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        if fan_mode == FAN_OFF:
            await self._client.change_blower(self._client.BLOWER_OFF)
        elif fan_mode == FAN_LOW:
            await self._client.change_blower(self._client.BLOWER_LOW)
        elif fan_mode == FAN_MEDIUM:
            await self._client.change_blower(self._client.BLOWER_MEDIUM)
        elif fan_mode == FAN_HIGH:
            await self._client.change_blower(self._client.BLOWER_HIGH)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode.

        OFF = Rest
        AUTO = Ready in Rest (can't be set, only reported)
        HEAT = Ready
        """
        if hvac_mode == HVAC_MODE_HEAT:
            await self._client.change_heatmode(self._client.HEATMODE_READY)
        else:
            await self._client.change_heatmode(self._client.HEATMODE_REST)

    def get_temp_unit(self):
        """Return the balboa equivalent temperature unit of the system."""
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return self._client.TSCALE_C
        return self._client.TSCALE_F
