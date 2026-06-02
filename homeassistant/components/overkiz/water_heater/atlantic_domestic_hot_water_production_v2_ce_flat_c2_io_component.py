"""Support for Atlantic Domestic Hot Water Production V2 CE FLAT C2 IO Component.

A heat-pump water heater (e.g. Thermor Malicio 2, Atlantic Explorer/Lineo,
Sauter Guelma), typically connected via a Cozytouch bridge.

It supports:
- Auto and manual operation modes (see OVERKIZ_TO_OPERATION_MODE).
- Boost ("performance"): activates the electrical coil to reach max
  temperature quickly, on top of the heat pump used in manual mode.
- Away mode: pauses heating while absent.
"""

from datetime import datetime, timedelta
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.water_heater import (
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..entity import OverkizEntity

DEFAULT_MIN_TEMP: float = 50.0
DEFAULT_MAX_TEMP: float = 70.0

# Away mode end date; 365 days (the app's maximum) keeps absence
# active until the user turns it off.
_AWAY_MODE_DURATION = timedelta(days=365)

STATE_AUTO = "auto"
STATE_MANUAL = "manual"

# Maps Overkiz DHW mode values to HA operation states:
# - autoMode: device manages heating from consumption history; no target temp.
# - manualEco(In)active: user sets the target temperature. Both map to "manual";
#   the eco flag is an internal device state, not user-selectable.
OVERKIZ_TO_OPERATION_MODE: dict[str, str] = {
    OverkizCommandParam.AUTO_MODE: STATE_AUTO,
    OverkizCommandParam.MANUAL_ECO_INACTIVE: STATE_MANUAL,
    OverkizCommandParam.MANUAL_ECO_ACTIVE: STATE_MANUAL,
}

# When setting manual mode, use manualEcoInactive (standard manual).
OPERATION_MODE_TO_OVERKIZ: dict[str, str] = {
    STATE_AUTO: OverkizCommandParam.AUTO_MODE,
    STATE_MANUAL: OverkizCommandParam.MANUAL_ECO_INACTIVE,
}


def _absence_date_parameter(value: datetime) -> list[str | int | float]:
    """Build the date parameter for the setAbsence(Start|End)Date commands.

    The cast can be removed once pyOverkiz fixes the parameter type to allow dicts.
    """
    return cast(
        list[str | int | float],
        [
            {
                "year": value.year,
                "month": value.month,
                "day": value.day,
                "hour": value.hour,
                "minute": value.minute,
                "second": value.second,
                "weekday": value.weekday(),
            }
        ],
    )


class AtlanticDomesticHotWaterProductionV2CEFLATC2IOComponent(
    OverkizEntity, WaterHeaterEntity
):
    """Representation of io:AtlanticDomesticHotWaterProductionV2_CE_FLAT_C2_IOComponent."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )
    _attr_operation_list = [*OPERATION_MODE_TO_OVERKIZ, STATE_PERFORMANCE]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if min_temp := self.device.states[
            OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE
        ]:
            return min_temp.value_as_float
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if max_temp := self.device.states[
            OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE
        ]:
            return max_temp.value_as_float
        return DEFAULT_MAX_TEMP

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if current_temp := self.device.states[OverkizState.IO_MIDDLE_WATER_TEMPERATURE]:
            return current_temp.value_as_float
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if target_temp := self.device.states[
            OverkizState.CORE_WATER_TARGET_TEMPERATURE
        ]:
            return target_temp.value_as_float
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE,
            temperature,
            refresh_afterwards=False,
        )
        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_WATER_TARGET_TEMPERATURE,
            refresh_afterwards=False,
        )
        await self.coordinator.async_refresh()

    @property
    def is_boost_mode_on(self) -> bool:
        """Return true if boost mode is on."""
        return (
            self.executor.select_state(OverkizState.IO_DHW_BOOST_MODE)
            == OverkizCommandParam.ON
        )

    @property
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on.

        io:DHWAbsenceModeState is 'off', 'on', or 'prog'.
        """
        return (
            self.executor.select_state(OverkizState.IO_DHW_ABSENCE_MODE)
            != OverkizCommandParam.OFF
        )

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        if self.is_boost_mode_on:
            return STATE_PERFORMANCE

        if dhw_mode := self.device.states[OverkizState.IO_DHW_MODE]:
            return OVERKIZ_TO_OPERATION_MODE.get(dhw_mode.value_as_str)

        return None

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == STATE_PERFORMANCE:
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off(refresh_afterwards=False)

            await self._async_turn_boost_mode_on()
            await self.coordinator.async_refresh()

            return

        previous_operation = self.current_operation

        # Disable boost and away before changing DHW mode
        if self.is_boost_mode_on:
            await self._async_turn_boost_mode_off()
        if self.is_away_mode_on:
            await self.async_turn_away_mode_off(refresh_afterwards=False)

        await self.executor.async_execute_command(
            OverkizCommand.SET_DHW_MODE,
            OPERATION_MODE_TO_OVERKIZ[operation_mode],
            refresh_afterwards=False,
        )

        # Switching from auto changes the target temperature, so refresh it.
        if previous_operation == STATE_AUTO:
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_WATER_TARGET_TEMPERATURE,
                refresh_afterwards=False,
            )

        await self.coordinator.async_refresh()

    async def async_turn_away_mode_on(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode on.

        Sets absence start/end dates and 'prog' mode in a single batch.
        'on' (permanent absence) is not recognized by the official app
        which causes a state mismatch, so 'prog' with a far-future end is used.
        """
        now = dt_util.now()
        end = now + _AWAY_MODE_DURATION

        await self.executor.async_execute_commands(
            [
                Command(
                    OverkizCommand.SET_ABSENCE_START_DATE,
                    _absence_date_parameter(now),
                ),
                Command(
                    OverkizCommand.SET_ABSENCE_END_DATE,
                    _absence_date_parameter(end),
                ),
                Command(
                    OverkizCommand.SET_ABSENCE_MODE,
                    [OverkizCommandParam.PROG],
                ),
            ],
            refresh_afterwards=refresh_afterwards,
        )

    async def async_turn_away_mode_off(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode off."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_MODE,
            OverkizCommandParam.OFF,
            refresh_afterwards=refresh_afterwards,
        )

    async def _async_turn_boost_mode_on(self) -> None:
        """Turn boost mode on.

        Refreshes the boost start/end dates, then activates boost
        with setBoostMode('on').
        """
        await self.executor.async_execute_commands(
            [
                Command(OverkizCommand.REFRESH_BOOST_START_DATE),
                Command(OverkizCommand.REFRESH_BOOST_END_DATE),
                Command(OverkizCommand.SET_BOOST_MODE, [OverkizCommandParam.ON]),
            ],
            refresh_afterwards=False,
        )

    async def _async_turn_boost_mode_off(self) -> None:
        """Turn boost mode off."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_BOOST_MODE,
            OverkizCommandParam.OFF,
            refresh_afterwards=False,
        )
