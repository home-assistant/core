"""Support for AtlanticDomesticHotWaterProductionMBLComponent."""

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

from .. import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity


class AtlanticDomesticHotWaterProductionMBLComponent(OverkizEntity, WaterHeaterEntity):
    """Representation of AtlanticDomesticHotWaterProductionMBLComponent (modbuslink)."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )
    _attr_operation_list = [
        OverkizCommandParam.PERFORMANCE,
        OverkizCommandParam.ECO,
        OverkizCommandParam.MANUAL,
    ]

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self._attr_max_temp = cast(
            float,
            self.executor.select_state(
                OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE
            ),
        )
        self._attr_min_temp = cast(
            float,
            self.executor.select_state(
                OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE
            ),
        )

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
            OverkizCommand.SET_TARGET_DHW_TEMPERATURE, temperature
        )

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""
        return self.executor.select_state(OverkizState.MODBUSLINK_DHW_BOOST_MODE) in (
            OverkizCommandParam.ON,
            OverkizCommandParam.PROG,
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
    def current_operation(self) -> str:
        """Return current operation."""
        if self.is_away_mode_on:
            return STATE_OFF

        if self.is_boost_mode_on:
            return STATE_PERFORMANCE

        if self.is_eco_mode_on:
            return STATE_ECO

        if (
            cast(str, self.executor.select_state(OverkizState.MODBUSLINK_DHW_MODE))
            == OverkizCommandParam.MANUAL_ECO_INACTIVE
        ):
            return OverkizCommandParam.MANUAL

        return STATE_OFF

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode in (STATE_PERFORMANCE, OverkizCommandParam.BOOST):
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off()
            await self.async_turn_boost_mode_on()
        elif operation_mode in (
            OverkizCommandParam.ECO,
            OverkizCommandParam.MANUAL_ECO_ACTIVE,
        ):
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off()
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off()
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE, OverkizCommandParam.AUTO_MODE
            )
        elif operation_mode in (
            OverkizCommandParam.MANUAL,
            OverkizCommandParam.MANUAL_ECO_INACTIVE,
        ):
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off()
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off()
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE, OverkizCommandParam.MANUAL_ECO_INACTIVE
            )
        else:
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off()
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off()
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
        """Turn boost mode on."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_BOOST_MODE, OverkizCommandParam.ON
        )

    async def async_turn_boost_mode_off(self) -> None:
        """Turn boost mode off."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_BOOST_MODE, OverkizCommandParam.OFF
        )
