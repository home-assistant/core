"""Support for Atlantic Pass APC Zone Control."""

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HEAT_PUMP,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..entity import OverkizEntity

OPERATION_LIST = [STATE_OFF, STATE_HEAT_PUMP, STATE_PERFORMANCE]


class AtlanticPassAPCDHW(OverkizEntity, WaterHeaterEntity):
    """Representation of Atlantic Pass APC DHW."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )
    _attr_operation_list = OPERATION_LIST

    @property
    def target_temperature(self) -> float:
        """Return the temperature corresponding to the PRESET."""
        if self.is_boost_mode_on:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_COMFORT_TARGET_DWH_TEMPERATURE
                ),
            )

        if self.is_eco_mode_on:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_ECO_TARGET_DWH_TEMPERATURE
                ),
            )

        return cast(
            float,
            self.executor.select_state(
                OverkizState.CORE_COMFORT_TARGET_DWH_TEMPERATURE
            ),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        if self.is_eco_mode_on:
            commands = [
                Command(
                    OverkizCommand.SET_ECO_TARGET_DHW_TEMPERATURE,
                    [temperature],
                ),
                Command(OverkizCommand.REFRESH_ECO_TARGET_DWH_TEMPERATURE),
                Command(OverkizCommand.REFRESH_TARGET_DWH_TEMPERATURE),
            ]
        else:
            commands = [
                Command(
                    OverkizCommand.SET_COMFORT_TARGET_DHW_TEMPERATURE,
                    [temperature],
                ),
                Command(OverkizCommand.REFRESH_COMFORT_TARGET_DWH_TEMPERATURE),
                Command(OverkizCommand.REFRESH_TARGET_DWH_TEMPERATURE),
            ]
        await self.executor.async_execute_commands(commands)

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if away mode is on."""
        return (
            self.executor.select_state(OverkizState.CORE_BOOST_ON_OFF)
            == OverkizCommandParam.ON
        )

    @property
    def is_eco_mode_on(self) -> bool:
        """Return true if eco mode is on."""
        current_mode = self.executor.select_state(OverkizState.IO_PASS_APCDWH_MODE)

        return current_mode == OverkizCommandParam.ECO

    @property
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on."""
        return (
            self.executor.select_state(OverkizState.CORE_DWH_ON_OFF)
            == OverkizCommandParam.OFF
        )

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        if self.is_boost_mode_on:
            return STATE_PERFORMANCE
        if self.is_eco_mode_on:
            return STATE_ECO
        if self.is_away_mode_on:
            return STATE_OFF
        return STATE_HEAT_PUMP

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
