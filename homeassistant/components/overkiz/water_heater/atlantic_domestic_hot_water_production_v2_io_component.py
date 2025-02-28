"""Support for AtlanticDomesticHotWaterProductionV2IOComponent."""

import asyncio
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .. import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity
from ..number import BOOST_MODE_DURATION_DELAY as MODE_DELAY, OPERATING_MODE_DELAY

DEFAULT_MIN_TEMP: float = 50.0
DEFAULT_MAX_TEMP: float = 62.0


class AtlanticDomesticHotWaterProductionV2IOComponent(OverkizEntity, WaterHeaterEntity):
    """Representation of AtlanticDomesticHotWaterProductionV2IOComponent (io)."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )
    _attr_operation_list = [
        STATE_ECO,
        STATE_PERFORMANCE,
        STATE_HEAT_PUMP,
        STATE_ELECTRIC,
    ]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""

        min_temp = self.device.states[OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE]
        if min_temp:
            return cast(float, min_temp.value_as_float)
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""

        max_temp = self.device.states[OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE]
        if max_temp:
            return cast(float, max_temp.value_as_float)
        return DEFAULT_MAX_TEMP

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""

        return cast(
            float,
            self.executor.select_state(
                OverkizState.IO_MIDDLE_WATER_TEMPERATURE,
                OverkizState.MODBUSLINK_MIDDLE_WATER_TEMPERATURE,
            ),
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature corresponding to the PRESET."""

        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""

        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, temperature, refresh_afterwards=False
        )
        await asyncio.sleep(MODE_DELAY)  # wait 1 second to have the new temperature in

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_TARGET_TEMPERATURE, refresh_afterwards=False
        )
        await self.coordinator.async_refresh()

    @property
    def is_state_eco(self) -> bool:
        """Return true if eco mode is on."""

        return (
            self.executor.select_state(OverkizState.CORE_OPERATING_MODE)
            == OverkizCommandParam.ECO
            or self.executor.select_state(OverkizState.IO_DHW_MODE)
            == OverkizCommandParam.MANUAL_ECO_ACTIVE
        )

    @property
    def is_state_perfomance(self) -> bool:
        """Return true if performance mode is on."""

        return (
            self.executor.select_state(OverkizState.IO_DHW_MODE)
            == OverkizCommandParam.AUTO_MODE
            or self.executor.select_state(OverkizState.CORE_OPERATING_MODE)
            == OverkizCommandParam.AUTO
        )

    @property
    def is_state_heat_pump(self) -> bool:
        """Return true if heat pump mode is on."""

        return self.executor.select_state(
            OverkizState.IO_DHW_MODE
        ) == OverkizCommandParam.MANUAL_ECO_INACTIVE or self.executor.select_state(
            OverkizState.CORE_OPERATING_MODE
        ) in (
            OverkizCommandParam.MANUAL,
            OverkizCommandParam.NORMAL,
            OverkizCommandParam.ON,
            OverkizCommandParam.PROG,
            "program",  # TODO: pyoverkiz PR
        )

    @property
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on."""
        return (
            self.executor.select_state(OverkizState.CORE_OPERATING_MODE)
            in (
                "antifreeze",  # TODO: pyoverkiz PR
                OverkizCommandParam.AWAY,
                OverkizCommandParam.FROSTPROTECTION,
            )
            or (
                cast(
                    str, self.executor.select_state(OverkizState.IO_AWAY_MODE_DURATION)
                )
                == "always"
            )
            or (
                int(
                    cast(
                        str,
                        self.executor.select_state(OverkizState.IO_AWAY_MODE_DURATION),
                    )
                )
                > 0
            )
        )

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""

        if self.is_boost_mode_on:
            return STATE_ELECTRIC

        if self.is_state_eco:
            return STATE_ECO

        if self.is_state_perfomance:
            return STATE_PERFORMANCE

        if self.is_state_heat_pump:
            return STATE_HEAT_PUMP

        return None

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""
        return (
            cast(int, self.executor.select_state(OverkizState.CORE_BOOST_MODE_DURATION))
            > 0
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""

        if operation_mode == STATE_ECO:
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off(refresh_afterwards=False)
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off(refresh_afterwards=False)

            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE,
                OverkizCommandParam.MANUAL_ECO_ACTIVE,
                refresh_afterwards=False,
            )
            await self.coordinator.async_refresh()
        elif operation_mode == STATE_PERFORMANCE:
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off(refresh_afterwards=False)
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off(refresh_afterwards=False)

            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE,
                OverkizCommandParam.AUTO_MODE,
                refresh_afterwards=False,
            )
            await self.coordinator.async_refresh()
        elif operation_mode == STATE_HEAT_PUMP:
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off(refresh_afterwards=False)
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off(refresh_afterwards=False)

            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE,
                OverkizCommandParam.MANUAL_ECO_INACTIVE,
                refresh_afterwards=False,
            )
            await self.coordinator.async_refresh()
        elif operation_mode == STATE_ELECTRIC:
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off(refresh_afterwards=False)
            if not self.is_boost_mode_on:
                await self.async_turn_boost_mode_on(refresh_afterwards=False)
            await self.coordinator.async_refresh()

    async def async_turn_away_mode_on(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode on."""

        await self.executor.async_execute_command(
            OverkizCommand.SET_CURRENT_OPERATING_MODE,
            {
                OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                OverkizCommandParam.ABSENCE: OverkizCommandParam.ON,
            },
            refresh_afterwards=refresh_afterwards,
        )
        await asyncio.sleep(
            OPERATING_MODE_DELAY
        )  # wait 3 seconds to have the new duration in

        await self.executor.async_execute_command(
            "refreshAwayModeDuration",  # TODO: pyoverkiz PR
            refresh_afterwards=refresh_afterwards,
        )

    async def async_turn_away_mode_off(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode off."""

        await self.executor.async_execute_command(
            OverkizCommand.SET_CURRENT_OPERATING_MODE,
            {
                OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
            },
            refresh_afterwards=refresh_afterwards,
        )
        await asyncio.sleep(
            OPERATING_MODE_DELAY
        )  # wait 3 seconds to have the new duration in
        await self.executor.async_execute_command(
            "refreshAwayModeDuration",  # TODO: pyoverkiz PR
            refresh_afterwards=refresh_afterwards,
        )

    async def async_turn_boost_mode_on(self, refresh_afterwards: bool = True) -> None:
        """Turn boost mode on."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_BOOST_MODE_DURATION,
            7,
            refresh_afterwards=refresh_afterwards,
        )
        await asyncio.sleep(MODE_DELAY)  # wait one second to not overload the device
        await self.executor.async_execute_command(
            OverkizCommand.SET_CURRENT_OPERATING_MODE,
            {
                OverkizCommandParam.RELAUNCH: OverkizCommandParam.ON,
                OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
            },
            refresh_afterwards=refresh_afterwards,
        )
        await asyncio.sleep(
            OPERATING_MODE_DELAY
        )  # wait 3 seconds to have the new duration in
        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_BOOST_MODE_DURATION,
            refresh_afterwards=refresh_afterwards,
        )

    async def async_turn_boost_mode_off(self, refresh_afterwards: bool = True) -> None:
        """Turn boost mode off."""

        await self.executor.async_execute_command(
            OverkizCommand.SET_CURRENT_OPERATING_MODE,
            {
                OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
            },
            refresh_afterwards=refresh_afterwards,
        )
        await asyncio.sleep(OPERATING_MODE_DELAY)  # wait to have the new duration in
        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_BOOST_MODE_DURATION,
            refresh_afterwards=refresh_afterwards,
        )
