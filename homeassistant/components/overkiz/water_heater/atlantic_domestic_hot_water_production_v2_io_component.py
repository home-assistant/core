"""Support for AtlanticDomesticHotWaterProductionV2IOComponent."""

from typing import Any, cast, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..entity import OverkizEntity

DEFAULT_MIN_TEMP: float = 50.0
DEFAULT_MAX_TEMP: float = 62.0
MAX_BOOST_MODE_DURATION: int = 7

DHWP_AWAY_MODES = [
    OverkizCommandParam.ABSENCE,
    OverkizCommandParam.AWAY,
    OverkizCommandParam.FROSTPROTECTION,
]


class AtlanticDomesticHotWaterProductionV2IOComponent(OverkizEntity, WaterHeaterEntity):
    """Representation of AtlanticDomesticHotWaterProductionV2IOComponent (io)."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )
    _attr_operation_list = [
        STATE_ECO,
        STATE_PERFORMANCE,
        STATE_HEAT_PUMP,
        STATE_ELECTRIC,
    ]

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""

        min_temp = self.device.states.get(
            OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE
        )
        if min_temp:
            return cast(float, min_temp.value_as_float)
        return DEFAULT_MIN_TEMP

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""

        max_temp = self.device.states.get(
            OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE
        )
        if max_temp:
            return cast(float, max_temp.value_as_float)
        return DEFAULT_MAX_TEMP

    @property
    @override
    def native_current_temperature(self) -> float:
        """Return the current temperature."""

        return cast(
            float,
            self.device.states.get_value(
                OverkizState.IO_MIDDLE_WATER_TEMPERATURE,
            ),
        )

    @property
    @override
    def native_target_temperature(self) -> float:
        """Return the temperature corresponding to the PRESET."""

        return cast(
            float,
            self.device.states.get_value(OverkizState.CORE_TARGET_TEMPERATURE),
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""

        temperature = kwargs[ATTR_TEMPERATURE]
        await self.executor.async_execute_commands(
            [
                Command(
                    name=OverkizCommand.SET_TARGET_TEMPERATURE,
                    parameters=[temperature],
                ),
                Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE),
            ]
        )

    @property
    def is_state_eco(self) -> bool:
        """Return true if eco mode is on."""

        return (
            self.device.states.get_value(OverkizState.IO_DHW_MODE)
            == OverkizCommandParam.MANUAL_ECO_ACTIVE
        )

    @property
    def is_state_performance(self) -> bool:
        """Return true if performance mode is on."""

        return (
            self.device.states.get_value(OverkizState.IO_DHW_MODE)
            == OverkizCommandParam.AUTO_MODE
        )

    @property
    def is_state_heat_pump(self) -> bool:
        """Return true if heat pump mode is on."""

        return (
            self.device.states.get_value(OverkizState.IO_DHW_MODE)
            == OverkizCommandParam.MANUAL_ECO_INACTIVE
        )

    @property
    @override
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on."""

        away_mode_duration = self.device.states.get_value(
            OverkizState.IO_AWAY_MODE_DURATION
        )
        if away_mode_duration is None:
            return False

        away_mode_duration = cast(str, away_mode_duration)
        # away_mode_duration can be either a Literal["always"]
        if away_mode_duration == OverkizCommandParam.ALWAYS:
            return True

        # Or an int of 0 to 7 days. But it still is a string.
        if away_mode_duration.isdecimal() and int(away_mode_duration) > 0:
            return True

        return False

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current operation."""

        # The Away Mode leaves the current operation unchanged
        if self.is_boost_mode_on:
            return STATE_ELECTRIC

        if self.is_state_eco:
            return STATE_ECO

        if self.is_state_performance:
            return STATE_PERFORMANCE

        if self.is_state_heat_pump:
            return STATE_HEAT_PUMP

        return None

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""

        boost_mode_duration = self.device.states.get_value(
            OverkizState.CORE_BOOST_MODE_DURATION
        )
        if boost_mode_duration is None:
            return False

        return cast(int, boost_mode_duration) > 0

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        commands: list[Command] = []

        if operation_mode == STATE_ECO:
            if self.is_boost_mode_on:
                commands.extend(self._boost_mode_off_commands())

            if self.is_away_mode_on:
                commands.extend(self._away_mode_commands(OverkizCommandParam.OFF))

            commands.append(
                Command(
                    name=OverkizCommand.SET_DHW_MODE,
                    parameters=[OverkizCommandParam.MANUAL_ECO_ACTIVE],
                )
            )
            # ECO changes the target temperature so we have to refresh it
            commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))

        elif operation_mode == STATE_PERFORMANCE:
            if self.is_boost_mode_on:
                commands.extend(self._boost_mode_off_commands())
            if self.is_away_mode_on:
                commands.extend(self._away_mode_commands(OverkizCommandParam.OFF))

            commands.append(
                Command(
                    name=OverkizCommand.SET_DHW_MODE,
                    parameters=[OverkizCommandParam.AUTO_MODE],
                )
            )

        elif operation_mode == STATE_HEAT_PUMP:
            if self.is_boost_mode_on:
                commands.extend(self._boost_mode_off_commands())
            if self.is_away_mode_on:
                commands.extend(self._away_mode_commands(OverkizCommandParam.OFF))

            commands.append(
                Command(
                    name=OverkizCommand.SET_DHW_MODE,
                    parameters=[OverkizCommandParam.MANUAL_ECO_INACTIVE],
                )
            )

            # Switching from STATE_PERFORMANCE to
            # STATE_HEAT_PUMP changes the target temperature
            # and requires a target temperature refresh
            if self.is_state_performance:
                commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))

        elif operation_mode == STATE_ELECTRIC:
            if self.is_away_mode_on:
                commands.extend(self._away_mode_commands(OverkizCommandParam.OFF))
            if not self.is_boost_mode_on:
                commands.extend(self._boost_mode_on_commands())

        await self.executor.async_execute_commands(commands)

    @override
    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.executor.async_execute_commands(
            self._away_mode_commands(OverkizCommandParam.ON)
        )

    @override
    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self.executor.async_execute_commands(
            self._away_mode_commands(OverkizCommandParam.OFF)
        )

    def _away_mode_commands(self, absence: OverkizCommandParam) -> list[Command]:
        """Return the commands that turn away mode on or off."""
        return [
            Command(
                name=OverkizCommand.SET_CURRENT_OPERATING_MODE,
                parameters=[
                    {
                        OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                        OverkizCommandParam.ABSENCE: absence,
                    }
                ],
            ),
            # Toggling the AWAY mode changes away mode duration so we have to refresh it
            Command(name=OverkizCommand.REFRESH_AWAY_MODE_DURATION),
        ]

    def _boost_mode_on_commands(self) -> list[Command]:
        """Return the commands that turn boost mode on."""
        commands = [
            Command(
                name=OverkizCommand.SET_BOOST_MODE_DURATION,
                parameters=[MAX_BOOST_MODE_DURATION],
            ),
            Command(
                name=OverkizCommand.SET_CURRENT_OPERATING_MODE,
                parameters=[
                    {
                        OverkizCommandParam.RELAUNCH: OverkizCommandParam.ON,
                        OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
                    }
                ],
            ),
            Command(name=OverkizCommand.REFRESH_BOOST_MODE_DURATION),
        ]

        # Switching from STATE_PERFORMANCE to BOOST requires
        # a target temperature refresh
        if self.is_state_performance:
            commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))

        return commands

    def _boost_mode_off_commands(self) -> list[Command]:
        """Return the commands that turn boost mode off."""
        return [
            Command(
                name=OverkizCommand.SET_CURRENT_OPERATING_MODE,
                parameters=[
                    {
                        OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                        OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
                    }
                ],
            ),
            # Toggling the BOOST mode changes boost mode duration so we have to refresh it
            Command(name=OverkizCommand.REFRESH_BOOST_MODE_DURATION),
        ]
