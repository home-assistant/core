"""Support for ESPHome climate devices."""
import logging
from typing import List, Optional

from aioesphomeapi import ClimateInfo, ClimateMode, ClimateState

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
    PRESET_AWAY,
    HVAC_MODE_OFF,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)

from . import (
    EsphomeEntity,
    esphome_map_enum,
    esphome_state_property,
    platform_async_setup_entry,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up ESPHome climate devices based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="climate",
        info_type=ClimateInfo,
        entity_type=EsphomeClimateDevice,
        state_type=ClimateState,
    )


@esphome_map_enum
def _climate_modes():
    return {
        ClimateMode.OFF: HVAC_MODE_OFF,
        ClimateMode.AUTO: HVAC_MODE_HEAT_COOL,
        ClimateMode.COOL: HVAC_MODE_COOL,
        ClimateMode.HEAT: HVAC_MODE_HEAT,
    }


class EsphomeClimateDevice(EsphomeEntity, ClimateDevice):
    """A climate implementation for ESPHome."""

    @property
    def _static_info(self) -> ClimateInfo:
        return super()._static_info

    @property
    def _state(self) -> Optional[ClimateState]:
        return super()._state

    @property
    def precision(self) -> float:
        """Return the precision of the climate device."""
        precicions = [PRECISION_WHOLE, PRECISION_HALVES, PRECISION_TENTHS]
        for prec in precicions:
            if self._static_info.visual_temperature_step >= prec:
                return prec
        # Fall back to highest precision, tenths
        return PRECISION_TENTHS

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available operation modes."""
        return [
            _climate_modes.from_esphome(mode)
            for mode in self._static_info.supported_modes
        ]

    @property
    def preset_modes(self):
        """Return preset modes."""
        return [PRESET_AWAY] if self._static_info.supports_away else []

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        # Round to one digit because of floating point math
        return round(self._static_info.visual_temperature_step, 1)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._static_info.visual_min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._static_info.visual_max_temperature

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        features = 0
        if self._static_info.supports_two_point_target_temperature:
            features |= SUPPORT_TARGET_TEMPERATURE_RANGE
        else:
            features |= SUPPORT_TARGET_TEMPERATURE
        if self._static_info.supports_away:
            features |= SUPPORT_PRESET_MODE
        return features

    @esphome_state_property
    def hvac_mode(self) -> Optional[str]:
        """Return current operation ie. heat, cool, idle."""
        return _climate_modes.from_esphome(self._state.mode)

    @esphome_state_property
    def preset_mode(self):
        """Return current preset mode."""
        return PRESET_AWAY if self._state.away else None

    @esphome_state_property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._state.current_temperature

    @esphome_state_property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._state.target_temperature

    @esphome_state_property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return self._state.target_temperature_low

    @esphome_state_property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        return self._state.target_temperature_high

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature (and operation mode if set)."""
        data = {"key": self._static_info.key}
        if ATTR_HVAC_MODE in kwargs:
            data["mode"] = _climate_modes.from_hass(kwargs[ATTR_HVAC_MODE])
        if ATTR_TEMPERATURE in kwargs:
            data["target_temperature"] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs:
            data["target_temperature_low"] = kwargs[ATTR_TARGET_TEMP_LOW]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            data["target_temperature_high"] = kwargs[ATTR_TARGET_TEMP_HIGH]
        await self._client.climate_command(**data)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        await self._client.climate_command(
            key=self._static_info.key, mode=_climate_modes.from_hass(hvac_mode)
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        away = preset_mode == PRESET_AWAY
        await self._client.climate_command(key=self._static_info.key, away=away)
