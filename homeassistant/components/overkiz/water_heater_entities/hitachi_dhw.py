"""Support for Hitachi DHW."""

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS

from ..entity import OverkizEntity

OVERKIZ_TO_OPERATION_MODE: dict[str, str] = {
    OverkizCommandParam.STANDARD: STATE_ECO,
    OverkizCommandParam.HIGH_DEMAND: STATE_HIGH_DEMAND,
    OverkizCommandParam.STOP: STATE_OFF,
}

OPERATION_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_OPERATION_MODE.items()}


class HitachiDHW(OverkizEntity, WaterHeaterEntity):
    """Representation of Hitachi DHW."""

    _attr_min_temp = 30.0
    _attr_max_temp = 70.0
    _attr_precision = PRECISION_WHOLE

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [*OPERATION_MODE_TO_OVERKIZ]

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return cast(
            float, self.executor.select_state(OverkizState.CORE_DHW_TEMPERATURE)
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return cast(
            float,
            self.executor.select_state(
                OverkizState.MODBUS_CONTROL_DHW_SETTING_TEMPERATURE
            ),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.executor.async_execute_command(
            OverkizCommand.SET_CONTROL_DHW_SETTING_TEMPERATURE, cast(int, temperature)
        )

    @property
    def current_operation(self) -> str:
        """Return current operation ie. eco, electric, performance, ..."""
        if (
            self.executor.select_state(OverkizState.MODBUS_CONTROL_DHW)
            == OverkizCommandParam.STOP
        ):
            return STATE_OFF

        return OVERKIZ_TO_OPERATION_MODE[
            cast(str, self.executor.select_state(OverkizState.MODBUS_DHW_MODE))
        ]

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        # Turn water heater off
        if operation_mode == OverkizCommandParam.OFF:
            return await self.executor.async_execute_command(
                OverkizCommand.SET_CONTROL_DHW, OverkizCommandParam.STOP
            )

        # Turn water heater on, when off
        if self.current_operation == OverkizCommandParam.OFF:
            await self.executor.async_execute_command(
                OverkizCommand.SET_CONTROL_DHW, OverkizCommandParam.ON
            )

        # Change operation mode
        await self.executor.async_execute_command(
            OverkizCommand.SET_DHW_MODE, OPERATION_MODE_TO_OVERKIZ[operation_mode]
        )
