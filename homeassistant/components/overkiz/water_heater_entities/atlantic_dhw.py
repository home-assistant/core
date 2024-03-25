"""Support for Atlantic Pass APC DHW."""

import logging
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..entity import OverkizEntity

OVERKIZ_TO_OPERATION_MODE: dict[str, str] = {
    STATE_PERFORMANCE: STATE_PERFORMANCE,
    STATE_ECO: OverkizCommandParam.MANUAL_ECO_ACTIVE,
    OverkizCommandParam.MANUAL: OverkizCommandParam.MANUAL_ECO_INACTIVE,
}

_LOGGER = logging.getLogger(__name__)


class AtlanticDHW(OverkizEntity, WaterHeaterEntity):
    """Representation of Atlantic Water Heater."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )
    _attr_operation_list = [*OVERKIZ_TO_OPERATION_MODE.keys()]
    _attr_min_temp = 50.0
    _attr_max_temp = 65.0

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return cast(
            float,
            self.executor.select_state(
                OverkizState.MODBUSLINK_MIDDLE_WATER_TEMPERATURE
            ),
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature corresponding to the PRESET."""
        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_WATER_TARGET_TEMPERATURE),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self.executor.async_execute_command(
            "setTargetDHWTemperature", temperature
        )

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""
        return (
            self.executor.select_state(OverkizState.MODBUSLINK_DHW_BOOST_MODE)
            == OverkizCommandParam.ON
        )

    @property
    def is_eco_mode_on(self) -> bool:
        """Return true if eco mode is on."""
        return self.executor.select_state(OverkizState.MODBUSLINK_DHW_MODE) in (
            OverkizCommandParam.MANUAL_ECO_ACTIVE,
            OverkizCommandParam.AUTO_MODE,
        )

    @property
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on."""
        return (
            self.executor.select_state(OverkizState.MODBUSLINK_DHW_ABSENCE_MODE)
            == OverkizCommandParam.ON
        )

    @property
    def dhw_mode(self) -> str:
        """Return DWH mode."""
        return cast(str, self.executor.select_state(OverkizState.MODBUSLINK_DHW_MODE))

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        if self.is_boost_mode_on:
            output = STATE_PERFORMANCE
        elif self.is_eco_mode_on:
            output = STATE_ECO
        elif self.is_away_mode_on:
            output = STATE_OFF
        elif (mode := self.dhw_mode) == OverkizCommandParam.MANUAL_ECO_INACTIVE:
            output = OverkizCommandParam.MANUAL
        else:
            output = mode

        return output

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode in (STATE_PERFORMANCE, OverkizCommandParam.BOOST):
            await self.async_turn_away_mode_off()
            await self.async_turn_boost_mode_on()
        elif operation_mode in (
            OverkizCommandParam.ECO,
            OverkizCommandParam.MANUAL_ECO_ACTIVE,
        ):
            await self.async_turn_away_mode_off()
            await self.async_turn_boost_mode_off()
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE, OverkizCommandParam.AUTO_MODE
            )
        elif operation_mode in (
            OverkizCommandParam.MANUAL,
            OverkizCommandParam.MANUAL_ECO_INACTIVE,
        ):
            await self.async_turn_away_mode_off()
            await self.async_turn_boost_mode_off()
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE, OverkizCommandParam.MANUAL_ECO_INACTIVE
            )
        else:
            await self.async_turn_boost_mode_off()
            await self.async_turn_away_mode_off()
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE, operation_mode
            )

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_MODE, OverkizCommandParam.ON
        )

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_MODE, OverkizCommandParam.OFF
        )

    async def async_turn_boost_mode_on(self) -> None:
        """Turn away mode on."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_BOOST_MODE, OverkizCommandParam.ON
        )

    async def async_turn_boost_mode_off(self) -> None:
        """Turn away mode off."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_BOOST_MODE, OverkizCommandParam.OFF
        )
