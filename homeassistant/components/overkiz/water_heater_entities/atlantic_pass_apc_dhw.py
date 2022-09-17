"""Support for Atlantic Pass APC Zone Control."""
from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import STATE_OFF, TEMP_CELSIUS

from ..entity import OverkizEntity

OPERATION_LIST = [STATE_OFF, STATE_HEAT_PUMP, STATE_PERFORMANCE]


class AtlanticPassAPCDHW(OverkizEntity, WaterHeaterEntity):
    """Representation of Atlantic Pass APC DHW."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.OPERATION_MODE | WaterHeaterEntityFeature.AWAY_MODE
    )
    _attr_operation_list = OPERATION_LIST

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        if self.is_boost_mode_on:
            return STATE_PERFORMANCE
        if self.is_away_mode_on:
            return STATE_OFF
        return STATE_HEAT_PUMP

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if away mode is on."""
        return (
            self.executor.select_state(OverkizState.CORE_BOOST_ON_OFF)
            == OverkizCommandParam.ON
        )

    @property
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on."""
        return (
            self.executor.select_state(OverkizState.CORE_DWH_ON_OFF)
            == OverkizCommandParam.OFF
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""

        boost_state = OverkizCommandParam.OFF
        regular_state = OverkizCommandParam.OFF
        if operation_mode == STATE_PERFORMANCE:
            boost_state = OverkizCommandParam.ON
            regular_state = OverkizCommandParam.ON
        elif operation_mode == STATE_HEAT_PUMP:
            regular_state = OverkizCommandParam.ON

        commands = [
            Command(
                OverkizCommand.SET_BOOST_ON_OFF_STATE,
                [boost_state],
            ),
            Command(
                OverkizCommand.SET_DHW_ON_OFF_STATE,
                [regular_state],
            ),
        ]
        await self.executor.async_execute_commands(commands)

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        commands = [
            Command(
                OverkizCommand.SET_BOOST_ON_OFF_STATE,
                [OverkizCommandParam.OFF],
            ),
            Command(
                OverkizCommand.SET_DHW_ON_OFF_STATE,
                [OverkizCommandParam.OFF],
            ),
        ]
        await self.executor.async_execute_commands(commands)

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        commands = [
            Command(
                OverkizCommand.SET_BOOST_ON_OFF_STATE,
                [OverkizCommandParam.OFF],
            ),
            Command(
                OverkizCommand.SET_DHW_ON_OFF_STATE,
                [OverkizCommandParam.ON],
            ),
        ]

        await self.executor.async_execute_commands(commands)
