"""Support for AtlanticDomesticHotWaterProductionMBLComponent."""

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.util import dt as dt_util

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
        STATE_ECO,
        STATE_OFF,
        STATE_PERFORMANCE,
        STATE_ELECTRIC,
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
        return self.executor.select_state(OverkizState.MODBUSLINK_DHW_ABSENCE_MODE) in (
            OverkizCommandParam.ON,
            OverkizCommandParam.PROG,
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
            # STATE_ELECTRIC is a substitution for OverkizCommandParam.MANUAL
            # to keep up with the conventional state usage only
            # https://developers.home-assistant.io/docs/core/entity/water-heater/#states
            return STATE_ELECTRIC

        return STATE_OFF

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == STATE_PERFORMANCE:
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off()
            await self.async_turn_boost_mode_on()
        elif operation_mode == STATE_ECO:
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off()
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off()
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE, OverkizCommandParam.AUTO_MODE
            )
        elif operation_mode == STATE_ELECTRIC:
            if self.is_away_mode_on:
                await self.async_turn_away_mode_off()
            if self.is_boost_mode_on:
                await self.async_turn_boost_mode_off()
            await self.executor.async_execute_command(
                OverkizCommand.SET_DHW_MODE, OverkizCommandParam.MANUAL_ECO_INACTIVE
            )
        elif operation_mode == STATE_OFF:
            await self.async_turn_away_mode_on()

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on.

        This requires the start date and the end date to be also set, and those dates have to match the device datetime.
        The API accepts setting dates in the format of the core:DateTimeState state for the DHW
        {'day': 11, 'hour': 21, 'minute': 12, 'month': 7, 'second': 53, 'weekday': 3, 'year': 2024}
        The dict is then passed as an actual device date, the away mode start date, and then as an end date,
        but with the year incremented by 1, so the away mode is getting turned on for the next year.
        The weekday number seems to have no effect so the calculation of the future date's weekday number is redundant,
        but possible via homeassistant dt_util to form both start and end dates dictionaries from scratch
        based on datetime.now() and datetime.timedelta into the future.
        If you execute `setAbsenceStartDate`, `setAbsenceEndDate` and `setAbsenceMode`,
        the API answers with "too many requests", as there's a polling update after each command execution,
        and the device becomes unavailable until the API is available again.
        With `refresh_afterwards=False` on the first commands, and `refresh_afterwards=True` only the last command,
        the API is not choking and the transition is smooth without the unavailability state.
        """
        now = dt_util.now()
        now_date = {
            "month": now.month,
            "hour": now.hour,
            "year": now.year,
            "weekday": now.weekday(),
            "day": now.day,
            "minute": now.minute,
            "second": now.second,
        }
        await self.executor.async_execute_command(
            OverkizCommand.SET_DATE_TIME,
            now_date,
            refresh_afterwards=False,
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_START_DATE, now_date, refresh_afterwards=False
        )
        now_date["year"] = now_date["year"] + 1
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_END_DATE, now_date, refresh_afterwards=False
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_MODE,
            OverkizCommandParam.PROG,
            refresh_afterwards=False,
        )
        await self.coordinator.async_refresh()

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
