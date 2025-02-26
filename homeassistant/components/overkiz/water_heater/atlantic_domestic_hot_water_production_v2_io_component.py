"""Support for AtlanticDomesticHotWaterProductionV2IOComponent."""

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .. import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

"""
HA state to device attribute

STATE_ECO
DHWModeState.manualEcoActive
OperatingModeState.eco

STATE_ELECTRIC
OperatingModeState.boost

STATE_HIGH_DEMAND
OperatingModeState.max

STATE_PERFORMANCE
DHWModeState.autoMode
OperatingModeState.auto

STATE_HEAT_PUMP
DHWModeState.manualEcoInactive
OperatingModeState.manual
OperatingModeState.normal
OperatingModeState.on
OperatingModeState.prog
OperatingModeState.program

AWAY_MODE
OperatingModeState.antifreeze
OperatingModeState.away
OperatingModeState.frostprotection

OFF
OperatingModeState.off
"""


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
        STATE_OFF,
        STATE_PERFORMANCE,
        STATE_ELECTRIC,
        STATE_HIGH_DEMAND,
        STATE_HEAT_PUMP,
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
    def is_state_electric(self) -> bool:
        """Return true if boost mode is on."""

        return (
            self.executor.select_state(OverkizState.CORE_OPERATING_MODE)
            == OverkizCommandParam.BOOST
        )

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
    def is_state_high_demand(self) -> bool:
        """Return true if high demand mode is on."""

        return (
            self.executor.select_state(OverkizState.CORE_OPERATING_MODE) == "max"
        )  # TODO: pyoverkiz PR

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

        return self.executor.select_state(OverkizState.CORE_OPERATING_MODE) in (
            "antifreeze",  # TODO: pyoverkiz PR
            OverkizCommandParam.AWAY,
            OverkizCommandParam.FROSTPROTECTION,
        )

    @property
    def is_off_mode(self) -> bool:
        """Return true if the mode is off."""

        return (
            self.executor.select_state(OverkizState.CORE_OPERATING_MODE)
            == OverkizCommandParam.OFF
        )

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""

        return cast(
            float,
            self.executor.select_state(OverkizState.IO_MIDDLE_WATER_TEMPERATURE),
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature corresponding to the PRESET."""

        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE),
        )

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""

        if self.is_away_mode_on:
            return STATE_OFF

        if self.is_off_mode:
            return STATE_OFF

        if self.is_state_electric:
            return STATE_ELECTRIC

        if self.is_state_eco:
            return STATE_ECO

        if self.is_state_high_demand:
            return STATE_HIGH_DEMAND

        if self.is_state_perfomance:
            return STATE_PERFORMANCE

        if self.is_state_heat_pump:
            return STATE_HEAT_PUMP

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""

        temperature = kwargs[ATTR_TEMPERATURE]
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, temperature
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""

        if operation_mode == STATE_OFF:
            await self.executor.async_execute_command(
                OverkizCommand.SET_CURRENT_OPERATING_MODE, OverkizCommandParam.OFF
            )
        elif operation_mode == STATE_ELECTRIC:
            await self.executor.async_execute_command(
                OverkizCommand.SET_CURRENT_OPERATING_MODE, OverkizCommandParam.BOOST
            )
        elif operation_mode == STATE_ECO:
            """
            DHWModeState.manualEcoActive
            OperatingModeState.eco
            """
            # TODO: choose one
            await self.executor.async_execute_command(
                OverkizCommand.SET_CURRENT_OPERATING_MODE,
                OverkizCommandParam.ECO,
                refresh_afterwards=False,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE,
                OverkizCommandParam.MANUAL_ECO_ACTIVE,
                refresh_afterwards=False,
            )
            await self.coordinator.async_refresh()
        elif operation_mode == STATE_HIGH_DEMAND:
            await self.executor.async_execute_command(
                OverkizCommand.SET_CURRENT_OPERATING_MODE,
                "max",  # TODO: pyoverkiz PR
            )
        elif operation_mode == STATE_PERFORMANCE:
            """
            DHWModeState.autoMode
            OperatingModeState.auto
            """
            # TODO: choose one
            await self.executor.async_execute_command(
                OverkizCommand.SET_CURRENT_OPERATING_MODE,
                OverkizCommandParam.AUTO,
                refresh_afterwards=False,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE,
                OverkizCommandParam.AUTO_MODE,
                refresh_afterwards=False,
            )
            await self.coordinator.async_refresh()
        elif operation_mode == STATE_HEAT_PUMP:
            """
            DHWModeState.manualEcoInactive
            OperatingModeState.manual
            OperatingModeState.normal
            OperatingModeState.on
            OperatingModeState.prog
            OperatingModeState.program
            """
            # TODO: choose one
            await self.executor.async_execute_command(
                OverkizCommand.SET_CURRENT_OPERATING_MODE,
                OverkizCommandParam.MANUAL,
                refresh_afterwards=False,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE,
                OverkizCommandParam.MANUAL_ECO_INACTIVE,
                refresh_afterwards=False,
            )
            await self.coordinator.async_refresh()

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""

        await self.executor.async_execute_command(
            OverkizCommand.SET_CURRENT_OPERATING_MODE, OverkizCommandParam.AWAY
        )

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""

        await self.set_operation_mode(STATE_ECO)
