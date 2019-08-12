"""Support for ESPHome climate devices."""
import logging
from typing import TYPE_CHECKING, List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_OPERATION_MODE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    STATE_AUTO, STATE_COOL, STATE_HEAT, SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_TEMPERATURE, PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE,
    STATE_OFF, TEMP_CELSIUS)

from . import EsphomeEntity, platform_async_setup_entry, \
    esphome_state_property, esphome_map_enum

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi import ClimateInfo, ClimateState, ClimateMode  # noqa

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up ESPHome climate devices based on a config entry."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import ClimateInfo, ClimateState  # noqa

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='climate',
        info_type=ClimateInfo, entity_type=EsphomeClimateDevice,
        state_type=ClimateState
    )


@esphome_map_enum
def _climate_modes():
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import ClimateMode  # noqa
    return {
        ClimateMode.OFF: STATE_OFF,
        ClimateMode.AUTO: STATE_AUTO,
        ClimateMode.COOL: STATE_COOL,
        ClimateMode.HEAT: STATE_HEAT,
    }


class EsphomeClimateDevice(EsphomeEntity, ClimateDevice):
    """A climate implementation for ESPHome."""

    @property
    def _static_info(self) -> 'ClimateInfo':
        return super()._static_info

    @property
    def _state(self) -> Optional['ClimateState']:
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
    def operation_list(self) -> List[str]:
        """Return the list of available operation modes."""
        return [
            _climate_modes.from_esphome(mode)
            for mode in self._static_info.supported_modes
        ]

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
        features = SUPPORT_OPERATION_MODE
        if self._static_info.supports_two_point_target_temperature:
            features |= (SUPPORT_TARGET_TEMPERATURE_LOW |
                         SUPPORT_TARGET_TEMPERATURE_HIGH)
        else:
            features |= SUPPORT_TARGET_TEMPERATURE
        if self._static_info.supports_away:
            features |= SUPPORT_AWAY_MODE
        return features

    @esphome_state_property
    def current_operation(self) -> Optional[str]:
        """Return current operation ie. heat, cool, idle."""
        return _climate_modes.from_esphome(self._state.mode)

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

    @esphome_state_property
    def is_away_mode_on(self) -> Optional[bool]:
        """Return true if away mode is on."""
        return self._state.away

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature (and operation mode if set)."""
        data = {'key': self._static_info.key}
        if ATTR_OPERATION_MODE in kwargs:
            data['mode'] = _climate_modes.from_hass(
                kwargs[ATTR_OPERATION_MODE])
        if ATTR_TEMPERATURE in kwargs:
            data['target_temperature'] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs:
            data['target_temperature_low'] = kwargs[ATTR_TARGET_TEMP_LOW]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            data['target_temperature_high'] = kwargs[ATTR_TARGET_TEMP_HIGH]
        await self._client.climate_command(**data)

    async def async_set_operation_mode(self, operation_mode) -> None:
        """Set new target operation mode."""
        await self._client.climate_command(
            key=self._static_info.key,
            mode=_climate_modes.from_hass(operation_mode),
        )

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self._client.climate_command(key=self._static_info.key,
                                           away=True)

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self._client.climate_command(key=self._static_info.key,
                                           away=False)
