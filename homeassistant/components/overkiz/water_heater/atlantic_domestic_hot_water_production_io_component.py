"""Support for AtlanticDomesticHotWaterProductionIOComponent."""

from typing import cast, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature

from ..const import DOMAIN
from ..entity import OverkizEntity

BOOST_MODE_DURATION: int = 7

STATE_AUTO = "auto"
STATE_MANUAL = "manual"

# io:DHWModeState values mapped to Home Assistant operation states.
OVERKIZ_TO_OPERATION_MODE: dict[str, str] = {
    OverkizCommandParam.AUTO_MODE: STATE_AUTO,
    OverkizCommandParam.MANUAL_ECO_ACTIVE: STATE_ECO,
    OverkizCommandParam.MANUAL_ECO_INACTIVE: STATE_MANUAL,
}

OPERATION_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_OPERATION_MODE.items()}


class AtlanticDomesticHotWaterProductionIOComponent(OverkizEntity, WaterHeaterEntity):
    """Representation of io:AtlanticDomesticHotWaterProductionIOComponent."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN
    _attr_supported_features = (
        WaterHeaterEntityFeature.OPERATION_MODE | WaterHeaterEntityFeature.AWAY_MODE
    )
    _attr_operation_list = [*OPERATION_MODE_TO_OVERKIZ, STATE_PERFORMANCE]

    # Target temperature is intentionally read-only. The device only accepts a
    # capacity-dependent set of discrete setpoints (e.g. on a 270 L tank: 50/54/58/62 °C,
    # one per "number of showers"), but the API advertises the setpoint as continuous with
    # no step or bounds, so any in-between value is silently ignored by the device.

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if current_temp := self.device.states.get(OverkizState.CORE_TEMPERATURE):
            return current_temp.value_as_float

        return None

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if target_temp := self.device.states.get(OverkizState.CORE_TARGET_TEMPERATURE):
            return target_temp.value_as_float

        return None

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""
        boost_duration = self.device.states.get_value(
            OverkizState.CORE_BOOST_MODE_DURATION
        )
        if boost_duration is None:
            return False

        return cast(int, boost_duration) > 0

    @property
    @override
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on."""
        away_duration = self.device.states.get_value(OverkizState.IO_AWAY_MODE_DURATION)
        if away_duration is None:
            return False

        away_duration = cast(str, away_duration)
        if away_duration == OverkizCommandParam.ALWAYS:
            return True

        return away_duration.isdecimal() and int(away_duration) > 0

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current operation."""
        if self.is_boost_mode_on:
            return STATE_PERFORMANCE

        if dhw_mode := self.device.states.get_value(OverkizState.IO_DHW_MODE):
            return OVERKIZ_TO_OPERATION_MODE.get(cast(str, dhw_mode))

        return None

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == STATE_PERFORMANCE:
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off(refresh_afterwards=False)

            await self._async_turn_boost_mode_on()
            await self.coordinator.async_refresh()
            return

        previous_operation = self.current_operation

        if self.is_boost_mode_on:
            await self._async_turn_boost_mode_off()

        if self.is_away_mode_on:
            await self.async_turn_away_mode_off(refresh_afterwards=False)

        commands = [
            Command(
                name=OverkizCommand.SET_DHW_MODE,
                parameters=[OPERATION_MODE_TO_OVERKIZ[operation_mode]],
            )
        ]
        # Leaving auto changes the target temperature, so refresh it.
        if previous_operation == STATE_AUTO:
            commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))

        await self.executor.async_execute_commands(commands)

    @override
    async def async_turn_away_mode_on(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode on."""
        await self.executor.async_execute_commands(
            [
                Command(
                    name=OverkizCommand.SET_CURRENT_OPERATING_MODE,
                    parameters=[
                        {
                            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                            OverkizCommandParam.ABSENCE: OverkizCommandParam.ON,
                        }
                    ],
                ),
                Command(name=OverkizCommand.REFRESH_AWAY_MODE_DURATION),
            ],
            refresh_afterwards=refresh_afterwards,
        )

    @override
    async def async_turn_away_mode_off(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode off."""
        await self.executor.async_execute_commands(
            [
                Command(
                    name=OverkizCommand.SET_CURRENT_OPERATING_MODE,
                    parameters=[
                        {
                            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                            OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
                        }
                    ],
                ),
                Command(name=OverkizCommand.REFRESH_AWAY_MODE_DURATION),
            ],
            refresh_afterwards=refresh_afterwards,
        )

    async def _async_turn_boost_mode_on(self) -> None:
        """Turn boost mode on."""
        await self.executor.async_execute_commands(
            [
                Command(
                    name=OverkizCommand.SET_BOOST_MODE_DURATION,
                    parameters=[BOOST_MODE_DURATION],
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
            ],
            refresh_afterwards=False,
        )

    async def _async_turn_boost_mode_off(self) -> None:
        """Turn boost mode off."""
        await self.executor.async_execute_commands(
            [
                Command(
                    name=OverkizCommand.SET_CURRENT_OPERATING_MODE,
                    parameters=[
                        {
                            OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                            OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
                        }
                    ],
                ),
                Command(name=OverkizCommand.REFRESH_BOOST_MODE_DURATION),
            ],
            refresh_afterwards=False,
        )
