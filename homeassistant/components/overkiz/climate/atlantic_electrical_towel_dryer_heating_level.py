"""Support for Atlantic Electrical Towel Dryers driven by heating levels.

Some towel dryers (e.g. Atlantic Adélis 2 Digit) report the
AtlanticElectricalTowelDryer widget without the towel dryer commands, and are
driven like Atlantic electrical heaters.

Boost needs setHeatingLevelWithTimer. The gateway reports neither the boost
nor its end, so both are tracked here: at the end the device returns to the
level it had before. The gateway reports a stale level until a setHeatingLevel
resets its transitory timer. Until cancelHeatingLevel is sent, even after the
boost ran out, any setHeatingLevel fails with OVERRIDEMODE_ERROR.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Self, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_COMFORT1 = "comfort-1"
PRESET_COMFORT2 = "comfort-2"
PRESET_FROST_PROTECTION = "frost_protection"

OVERKIZ_TO_PRESET_MODE: dict[str, str] = {
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.COMFORT_1: PRESET_COMFORT1,
    OverkizCommandParam.COMFORT_2: PRESET_COMFORT2,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.FROSTPROTECTION: PRESET_FROST_PROTECTION,
    OverkizCommandParam.BOOST: PRESET_BOOST,
}
PRESET_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}

TEMPERATURE_SENSOR_DEVICE_INDEX = 7

BOOST_DURATION = timedelta(minutes=60)  # same as the boost button on the device
# The cancel fails once the boost is over, so it runs separately from the new level
CANCEL_SETTLE_DELAY = 5
TIMER_CANCELLED = 0
TIMER_LEVEL_SET = 65535


@dataclass
class TowelDryerExtraStoredData(ExtraStoredData):
    """Boost tracking, stored as the gateway does not report it."""

    assumed_level: str | None
    boost_until: datetime | None
    override_pending: bool

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored data."""
        return {
            "assumed_level": self.assumed_level,
            "boost_until": self.boost_until.isoformat() if self.boost_until else None,
            "override_pending": self.override_pending,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize the stored data from a dict."""
        try:
            assumed_level = restored["assumed_level"]
            boost_until = restored["boost_until"]
            override_pending = restored["override_pending"]
        except KeyError:
            return None
        return cls(
            assumed_level=assumed_level,
            boost_until=dt_util.parse_datetime(boost_until) if boost_until else None,
            override_pending=override_pending,
        )


class AtlanticElectricalTowelDryerHeatingLevel(
    OverkizEntity, ClimateEntity, RestoreEntity
):
    """Representation of an Atlantic towel dryer driven by heating levels."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [*PRESET_MODE_TO_OVERKIZ]
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_translation_key = DOMAIN

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self._lock = asyncio.Lock()
        self._boost_until: datetime | None = None
        self._unsub_boost_end: CALLBACK_TYPE | None = None
        # Level the device is on or returns to, while the gateway reports a stale one
        self._assumed_level: str | None = None
        # A level was sent and the gateway has not reported it yet
        self._level_pending = False
        # A boost was started and has not been cancelled, even if it ran out
        self._override_pending = False
        # The gateway reported the timer of the boost started from Home Assistant
        self._boost_timer_seen = False

    def _state(self, name: str) -> Any:
        """Return the raw value of a device state, or None."""
        state = self.device.states.get(name)
        return state.value if state is not None else None

    @property
    def _boost_end(self) -> datetime | None:
        """Return the end of the boost started from Home Assistant, if running."""
        if self._boost_until is not None and dt_util.utcnow() < self._boost_until:
            return self._boost_until
        return None

    @property
    def _transitory_timer(self) -> int | None:
        """Return the transitory timer of the gateway."""
        try:
            return int(self._state(OverkizState.IO_TIMER_FOR_TRANSITORY_STATE))
        except TypeError, ValueError:
            return None

    @property
    def _boost_override(self) -> bool:
        """Return True while the gateway still holds a boost override."""
        return self._transitory_timer not in (None, TIMER_CANCELLED, TIMER_LEVEL_SET)

    @property
    def _reported_level(self) -> str:
        """Return the heating level reported by the gateway."""
        return str(self._state(OverkizState.IO_TARGET_HEATING_LEVEL))

    @property
    def _level(self) -> str:
        """Return the heating level the device is on."""
        if self._assumed_level is not None and (
            self._level_pending or self._transitory_timer != TIMER_LEVEL_SET
        ):
            return self._assumed_level
        return self._reported_level

    def _clear_boost(self) -> None:
        """Forget the running boost."""
        self._boost_until = None
        self._boost_timer_seen = False
        if self._unsub_boost_end:
            self._unsub_boost_end()
            self._unsub_boost_end = None

    @callback
    def _boost_ended(self, _now: datetime) -> None:
        """Refresh the state when the boost timer runs out."""
        self._unsub_boost_end = None
        self._boost_until = None
        self.async_write_ha_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Reconcile the tracked levels with the gateway."""
        if self._transitory_timer != TIMER_LEVEL_SET:
            if self._boost_until is not None:
                self._boost_timer_seen = True
        elif self._boost_timer_seen:
            # The boost was cancelled or replaced by another client
            self._clear_boost()
            self._override_pending = False
            self._level_pending = False
            self._assumed_level = None
        elif self._level_pending:
            if self._reported_level == self._assumed_level:
                self._level_pending = False
                self._assumed_level = None
        elif not self._override_pending:
            self._assumed_level = None
        super()._handle_coordinator_update()

    async def _async_set_level(self, level: str) -> None:
        """Set a heating level, cancelling a boost first."""
        async with self._lock:
            if (
                self._override_pending
                or self._boost_end is not None
                or self._boost_override
                or self._reported_level == OverkizCommandParam.BOOST
            ):
                await self.executor.async_execute_command(
                    OverkizCommand.CANCEL_HEATING_LEVEL, OverkizCommandParam.BOOST
                )
                self._override_pending = False
                await asyncio.sleep(CANCEL_SETTLE_DELAY)
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_LEVEL, level
            )
            self._clear_boost()
            self._assumed_level = level
            self._level_pending = True
            self.async_write_ha_state()

    async def _async_start_boost(self) -> None:
        """Start a timed boost."""
        async with self._lock:
            # The device returns to this level after the boost
            return_level = self._assumed_level
            if (
                return_level is None
                and self._transitory_timer == TIMER_LEVEL_SET
                and self._reported_level != OverkizCommandParam.BOOST
            ):
                return_level = self._reported_level
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_LEVEL_WITH_TIMER,
                OverkizCommandParam.BOOST,
                int(BOOST_DURATION.total_seconds() // 60),
            )
            self._clear_boost()
            self._assumed_level = return_level
            self._level_pending = False
            self._override_pending = True
            self._boost_until = dt_util.utcnow() + BOOST_DURATION
            self._unsub_boost_end = async_call_later(
                self.hass, BOOST_DURATION, self._boost_ended
            )
            self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the boost tracking."""
        await super().async_added_to_hass()
        if (extra_data := await self.async_get_last_extra_data()) is None or (
            data := TowelDryerExtraStoredData.from_dict(extra_data.as_dict())
        ) is None:
            return
        self._assumed_level = data.assumed_level
        self._override_pending = data.override_pending
        if data.boost_until is not None and data.boost_until > dt_util.utcnow():
            self._boost_until = data.boost_until
            self._unsub_boost_end = async_call_later(
                self.hass, data.boost_until - dt_util.utcnow(), self._boost_ended
            )

    @property
    @override
    def extra_restore_state_data(self) -> TowelDryerExtraStoredData:
        """Return the boost tracking to restore."""
        return TowelDryerExtraStoredData(
            assumed_level=self._assumed_level,
            boost_until=self._boost_until,
            override_pending=self._override_pending,
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel the boost timer."""
        self._clear_boost()
        await super().async_will_remove_from_hass()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the end of the running boost."""
        boost_end = self._boost_end
        return {"boost_end": boost_end.isoformat() if boost_end else None}

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self._boost_end is None and self._level == OverkizCommandParam.OFF:
            return HVACMode.OFF
        return HVACMode.HEAT

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self._async_set_level(
            OverkizCommandParam.OFF
            if hvac_mode == HVACMode.OFF
            else OverkizCommandParam.COMFORT
        )

    @property
    @override
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if (
            self._state(OverkizState.CORE_REGULATION_MODE)
            == OverkizCommandParam.INCREASE
        ):
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._boost_end is not None:
            return PRESET_BOOST
        level = self._level
        if level == OverkizCommandParam.BOOST:
            # Boost not started from Home Assistant and already over
            return PRESET_COMFORT
        return OVERKIZ_TO_PRESET_MODE.get(level)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            await self._async_start_boost()
            return
        await self._async_set_level(PRESET_MODE_TO_OVERKIZ[preset_mode])

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the target temperature."""
        value = self._state(OverkizState.CORE_TARGET_TEMPERATURE)
        return float(value) if value is not None else None

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Linked devices are replaced when the coordinator reconnects
        temperature_device = self.executor.linked_device(
            TEMPERATURE_SENSOR_DEVICE_INDEX
        )
        if temperature_device is None:
            return None
        state = temperature_device.states.get(OverkizState.CORE_TEMPERATURE)
        if state is None or state.value is None:
            return None
        return state.value_as_float

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_handle_set_hvac_mode_service(hvac_mode)
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, kwargs[ATTR_TEMPERATURE]
        )
