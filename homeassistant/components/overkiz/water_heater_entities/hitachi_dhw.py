"""Support for Hitachi DHW."""

from __future__ import annotations

from typing import Any

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_HIGH_DEMAND,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)

from ..entity import OverkizEntity

OVERKIZ_TO_OPERATION_MODE: dict[str, str] = {
    OverkizCommandParam.STANDARD: STATE_ON,
    OverkizCommandParam.HIGH_DEMAND: STATE_HIGH_DEMAND,
    OverkizCommandParam.STOP: STATE_OFF,
}

OPERATION_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_OPERATION_MODE.items()}


class HitachiDHW(OverkizEntity, WaterHeaterEntity):
    """Representation of Hitachi DHW."""

    _attr_min_temp = 30.0
    _attr_max_temp = 70.0
    _attr_precision = PRECISION_WHOLE

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [*OPERATION_MODE_TO_OVERKIZ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        current_temperature = self.device.states[OverkizState.CORE_DHW_TEMPERATURE]
        if current_temperature:
            return current_temperature.value_as_float
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        target_temperature = self.device.states[
            OverkizState.MODBUS_CONTROL_DHW_SETTING_TEMPERATURE
        ]
        if target_temperature:
            return target_temperature.value_as_float
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""

        await self.executor.async_execute_command(
            OverkizCommand.SET_CONTROL_DHW_SETTING_TEMPERATURE,
            int(kwargs[ATTR_TEMPERATURE]),
        )

    @property
    def current_operation(self) -> str | None:
        """Return current operation ie. eco, electric, performance, ..."""
        modbus_control = self.device.states[OverkizState.MODBUS_CONTROL_DHW]
        if modbus_control and modbus_control.value_as_str == OverkizCommandParam.STOP:
            return STATE_OFF

        current_mode = self.device.states[OverkizState.MODBUS_DHW_MODE]
        if current_mode and current_mode.value_as_str in OVERKIZ_TO_OPERATION_MODE:
            return OVERKIZ_TO_OPERATION_MODE[current_mode.value_as_str]

        return None

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        # Turn water heater off
        if operation_mode == OverkizCommandParam.OFF:
            await self.executor.async_execute_command(
                OverkizCommand.SET_CONTROL_DHW, OverkizCommandParam.STOP
            )
            return

        # Turn water heater on, when off
        if self.current_operation == OverkizCommandParam.OFF:
            await self.executor.async_execute_command(
                OverkizCommand.SET_CONTROL_DHW, OverkizCommandParam.ON
            )

        # Change operation mode
        await self.executor.async_execute_command(
            OverkizCommand.SET_DHW_MODE, OPERATION_MODE_TO_OVERKIZ[operation_mode]
        )
