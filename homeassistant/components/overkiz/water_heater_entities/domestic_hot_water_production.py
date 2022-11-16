"""Support for DomesticHotWaterProduction."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..entity import OverkizEntity

OVERKIZ_TO_OPERATION_MODE: dict[str, str] = {
    OverkizCommandParam.STANDARD: STATE_ECO,
    OverkizCommandParam.HIGH_DEMAND: STATE_HIGH_DEMAND,
    OverkizCommandParam.STOP: STATE_OFF,
    OverkizCommandParam.MANUAL_ECO_ACTIVE: STATE_ECO,
    OverkizCommandParam.MANUAL_ECO_INACTIVE: STATE_OFF,
    OverkizCommandParam.AUTO: STATE_ECO,
    OverkizCommandParam.AUTO_MODE: STATE_ECO,
    OverkizCommandParam.BOOST: STATE_PERFORMANCE,
}

OPERATION_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_OPERATION_MODE.items()}

DHWP_AWAY_MODES = [
    OverkizCommandParam.ABSENCE,
    OverkizCommandParam.AWAY,
    OverkizCommandParam.FROSTPROTECTION,
]

DHWP_BOOST_MODES = [
    OverkizCommandParam.BOOST,
]


class DomesticHotWaterProduction(OverkizEntity, WaterHeaterEntity):
    """Representation of a DomesticHotWaterProduction Water Heater."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [*OPERATION_MODE_TO_OVERKIZ]

    @property
    def _is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""

        if self.executor.has_state(OverkizState.IO_DHW_BOOST_MODE):
            return (
                self.executor.select_state(OverkizState.IO_DHW_BOOST_MODE)
                == OverkizCommandParam.ON
            )

        if self.executor.has_state(OverkizState.CORE_BOOST_MODE_DURATION):
            return (
                cast(
                    float,
                    self.executor.select_state(OverkizState.CORE_BOOST_MODE_DURATION),
                )
                > 0
            )

        operating_mode = self.executor.select_state(OverkizState.CORE_OPERATING_MODE)

        if operating_mode:
            if isinstance(operating_mode, dict):
                if operating_mode.get(OverkizCommandParam.RELAUNCH):
                    return (
                        cast(
                            str,
                            operating_mode.get(OverkizCommandParam.RELAUNCH),
                        )
                        == OverkizCommandParam.ON
                    )
                return False

            return cast(str, operating_mode) in DHWP_BOOST_MODES

        return False

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return true if away mode is on."""

        if self.executor.has_state(OverkizState.IO_DHW_ABSENCE_MODE):
            return (
                self.executor.select_state(OverkizState.IO_DHW_ABSENCE_MODE)
                == OverkizCommandParam.ON
            )

        if self.executor.has_state(OverkizState.MODBUSLINK_DHW_ABSENCE_MODE):
            return (
                self.executor.select_state(OverkizState.MODBUSLINK_DHW_ABSENCE_MODE)
                == OverkizCommandParam.ON
            )

        operating_mode = self.executor.select_state(OverkizState.CORE_OPERATING_MODE)

        if operating_mode:
            if isinstance(operating_mode, dict):
                if operating_mode.get(OverkizCommandParam.ABSENCE):
                    return (
                        cast(
                            str,
                            operating_mode.get(OverkizCommandParam.ABSENCE),
                        )
                        == OverkizCommandParam.ON
                    )
                if operating_mode.get(OverkizCommandParam.AWAY):
                    return (
                        cast(
                            str,
                            operating_mode.get(OverkizCommandParam.AWAY),
                        )
                        == OverkizCommandParam.ON
                    )
                return False

            return cast(str, operating_mode) in DHWP_AWAY_MODES

        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return cast(
            float,
            self.executor.select_state(
                OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE
            ),
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return cast(
            float,
            self.executor.select_state(
                OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE
            ),
        )

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
        """Return the temperature we try to reach."""
        return cast(
            float, self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)
        )

    @property
    def target_temperature_high(self) -> float:
        """Return the highbound target temperature we try to reach."""
        return cast(
            float,
            self.executor.select_state(
                OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE
            ),
        )

    @property
    def target_temperature_low(self) -> float:
        """Return the lowbound target temperature we try to reach."""
        return cast(
            float,
            self.executor.select_state(
                OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE
            ),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, target_temperature
        )

        if self.executor.has_command(OverkizCommand.REFRESH_TARGET_TEMPERATURE):
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_TARGET_TEMPERATURE
            )

    @property
    def current_operation(self) -> str:
        """Return current operation ie. eco, electric, performance, ..."""
        if self._is_boost_mode_on:
            return OVERKIZ_TO_OPERATION_MODE[OverkizCommandParam.BOOST]

        return OVERKIZ_TO_OPERATION_MODE[
            cast(
                str,
                self.executor.select_state(
                    OverkizState.IO_DHW_MODE, OverkizState.MODBUSLINK_DHW_MODE
                ),
            )
        ]

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""

        if operation_mode == STATE_PERFORMANCE:
            if self.executor.has_command(OverkizCommand.SET_BOOST_MODE):
                await self.executor.async_execute_command(
                    OverkizCommand.SET_BOOST_MODE, OverkizCommand.ON
                )

            if self.executor.has_command(OverkizCommand.SET_BOOST_MODE_DURATION):
                await self.executor.async_execute_command(
                    OverkizCommand.SET_BOOST_MODE_DURATION, 7
                )
                await self.executor.async_execute_command(
                    OverkizCommand.REFRESH_BOOST_MODE_DURATION
                )

            if self.executor.has_command(OverkizCommand.SET_CURRENT_OPERATING_MODE):
                current_operating_mode = self.executor.select_state(
                    OverkizState.CORE_OPERATING_MODE
                )

                if current_operating_mode and isinstance(current_operating_mode, dict):
                    await self.executor.async_execute_command(
                        OverkizCommand.SET_CURRENT_OPERATING_MODE,
                        {
                            OverkizCommandParam.RELAUNCH: OverkizCommandParam.ON,
                            OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
                        },
                    )

            return

        if self._is_boost_mode_on:
            if self.executor.has_command(OverkizCommand.SET_BOOST_MODE):
                await self.executor.async_execute_command(
                    OverkizCommand.SET_BOOST_MODE, OverkizCommand.OFF
                )

            if self.executor.has_command(OverkizCommand.SET_BOOST_MODE_DURATION):
                await self.executor.async_execute_command(
                    OverkizCommand.SET_BOOST_MODE_DURATION, 0
                )
                await self.executor.async_execute_command(
                    OverkizCommand.REFRESH_BOOST_MODE_DURATION
                )

            if self.executor.has_command(OverkizCommand.SET_CURRENT_OPERATING_MODE):
                current_operating_mode = self.executor.select_state(
                    OverkizState.CORE_OPERATING_MODE
                )

                if current_operating_mode and isinstance(current_operating_mode, dict):
                    await self.executor.async_execute_command(
                        OverkizCommand.SET_CURRENT_OPERATING_MODE,
                        {
                            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                            OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
                        },
                    )

        await self.executor.async_execute_command(
            OverkizCommand.SET_DHW_MODE, OPERATION_MODE_TO_OVERKIZ[operation_mode]
        )
