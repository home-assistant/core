"""Support for DomesticHotWaterProduction."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON, TEMP_CELSIUS

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

OVERKIZ_TO_OPERATION_MODE: dict[str, str] = {
    OverkizCommandParam.STANDARD: STATE_ON,
    OverkizCommandParam.HIGH_DEMAND: STATE_HIGH_DEMAND,
    OverkizCommandParam.STOP: STATE_OFF,
    OverkizCommandParam.MANUAL_ECO_ACTIVE: STATE_ECO,
    OverkizCommandParam.MANUAL_ECO_INACTIVE: STATE_OFF,
    OverkizCommandParam.ECO: STATE_ECO,
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

DEFAULT_MIN_TEMP: float = 30
DEFAULT_MAX_TEMP: float = 70


class DomesticHotWaterProduction(OverkizEntity, WaterHeaterEntity):
    """Representation of a DomesticHotWaterProduction Water Heater."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [*OPERATION_MODE_TO_OVERKIZ]

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        # Init operation mode to set for this specific device
        self.overkiz_to_operation_mode: dict[str, str] = {}
        state_mode_definition = self.executor.select_definition_state(
            OverkizState.IO_DHW_MODE, OverkizState.MODBUSLINK_DHW_MODE
        )
        if state_mode_definition and state_mode_definition.values:
            # Filter only for mode allowed by this device
            for param, mode in OVERKIZ_TO_OPERATION_MODE.items():
                if param in state_mode_definition.values:
                    self.overkiz_to_operation_mode[param] = mode
        else:
            self.overkiz_to_operation_mode = OVERKIZ_TO_OPERATION_MODE

    @property
    def _is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""

        if self.executor.has_state(OverkizState.IO_DHW_BOOST_MODE):
            return (
                self.executor.select_state(OverkizState.IO_DHW_BOOST_MODE)
                == OverkizCommandParam.ON
            )

        if self.executor.has_state(OverkizState.MODBUSLINK_DHW_BOOST_MODE):
            return (
                self.executor.select_state(OverkizState.MODBUSLINK_DHW_BOOST_MODE)
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

            return cast(str, operating_mode) == OverkizCommandParam.BOOST

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
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        current_temperature = self.device.states[
            OverkizState.IO_MIDDLE_WATER_TEMPERATURE
        ]
        if current_temperature:
            return current_temperature.value_as_float
        current_temperature = self.device.states[
            OverkizState.MODBUSLINK_MIDDLE_WATER_TEMPERATURE
        ]
        if current_temperature:
            return current_temperature.value_as_float
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""

        target_temperature = self.device.states[
            OverkizState.CORE_WATER_TARGET_TEMPERATURE
        ]
        if target_temperature:
            return target_temperature.value_as_float

        target_temperature = self.device.states[
            OverkizState.CORE_TARGET_DWH_TEMPERATURE
        ]
        if target_temperature:
            return target_temperature.value_as_float

        target_temperature = self.device.states[OverkizState.CORE_TARGET_TEMPERATURE]
        if target_temperature:
            return target_temperature.value_as_float

        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        target_temperature_high = self.device.states[
            OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE
        ]
        if target_temperature_high:
            return target_temperature_high.value_as_float
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        target_temperature_low = self.device.states[
            OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE
        ]
        if target_temperature_low:
            return target_temperature_low.value_as_float
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)

        if self.executor.has_command(OverkizCommand.SET_TARGET_TEMPERATURE):
            await self.executor.async_execute_command(
                OverkizCommand.SET_TARGET_TEMPERATURE, target_temperature
            )
        elif self.executor.has_command(OverkizCommand.SET_WATER_TARGET_TEMPERATURE):
            await self.executor.async_execute_command(
                OverkizCommand.SET_WATER_TARGET_TEMPERATURE, target_temperature
            )

        if self.executor.has_command(OverkizCommand.REFRESH_TARGET_TEMPERATURE):
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_TARGET_TEMPERATURE
            )
        elif self.executor.has_command(OverkizCommand.REFRESH_WATER_TARGET_TEMPERATURE):
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_WATER_TARGET_TEMPERATURE
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
            # We're setting a non Boost mode and the device is currently in Boost mode, the following code remove all boost operations
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
            OverkizCommand.SET_DHW_MODE, self.overkiz_to_operation_mode[operation_mode]
        )

        if self.executor.has_command(OverkizCommand.REFRESH_DHW_MODE):
            await self.executor.async_execute_command(OverkizCommand.REFRESH_DHW_MODE)
