"""Climate platform for the Daikin Infrared integration."""

from calendar import Day
from dataclasses import dataclass, replace
from datetime import datetime, time
from typing import Any, NamedTuple, Self, override

from infrared_protocols.commands.daikin_ac import (
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    DaikinAcBrightness,
    DaikinAcClock,
    DaikinAcComfort,
    DaikinAcCommand,
    DaikinAcFanSpeed,
    DaikinAcMode,
    DaikinAcState,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import (
    InfraredEmitterConsumerEntity,
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
)

PARALLEL_UPDATES = 1

# The unit leaves powerful mode on its own after 20 minutes.
BOOST_DURATION = 20 * 60

DEFAULT_TEMPERATURE = 24.0


class _TemperatureRange(NamedTuple):
    low: float
    high: float


# The setpoint range the remotes allow in each mode that has a setpoint
TEMPERATURE_RANGES: dict[DaikinAcMode, _TemperatureRange] = {
    DaikinAcMode.AUTO: _TemperatureRange(18, 30),
    DaikinAcMode.COOL: _TemperatureRange(18, 32),
    DaikinAcMode.HEAT: _TemperatureRange(10, 30),
}
# Dry and fan only have no setpoint, so only the protocol's limits apply
_FULL_RANGE = _TemperatureRange(MIN_TEMPERATURE, MAX_TEMPERATURE)

_HA_MODE_TO_LIB: dict[HVACMode, DaikinAcMode] = {
    HVACMode.HEAT_COOL: DaikinAcMode.AUTO,
    HVACMode.COOL: DaikinAcMode.COOL,
    HVACMode.HEAT: DaikinAcMode.HEAT,
    HVACMode.DRY: DaikinAcMode.DRY,
    HVACMode.FAN_ONLY: DaikinAcMode.FAN_ONLY,
}
_LIB_MODE_TO_HA = {v: k for k, v in _HA_MODE_TO_LIB.items()}

_HA_FAN_TO_LIB: dict[str, DaikinAcFanSpeed] = {
    FAN_AUTO: DaikinAcFanSpeed.AUTO,
    "silence": DaikinAcFanSpeed.SILENT,
    "1": DaikinAcFanSpeed.LEVEL_1,
    "2": DaikinAcFanSpeed.LEVEL_2,
    "3": DaikinAcFanSpeed.LEVEL_3,
    "4": DaikinAcFanSpeed.LEVEL_4,
    "5": DaikinAcFanSpeed.LEVEL_5,
}
_LIB_FAN_TO_HA = {v: k for k, v in _HA_FAN_TO_LIB.items()}


def _state_as_dict(state: DaikinAcState) -> dict[str, Any]:
    """Return the unit state in a form that can be stored."""
    return {
        "power": state.power,
        "mode": state.mode.name,
        "temperature": state.temperature,
        "fan": state.fan.name,
        "swing_v": state.swing_v,
        "swing_h": state.swing_h,
        "powerful": state.powerful,
        "econo": state.econo,
        "quiet": state.quiet,
        "sensor": state.sensor,
        "on_timer": state.on_timer.isoformat() if state.on_timer else None,
        "off_timer": state.off_timer.isoformat() if state.off_timer else None,
        "weekly_timer": state.weekly_timer,
    }


def _state_from_dict(stored: dict[str, Any]) -> DaikinAcState:
    """Rebuild the unit state from its stored form.

    Raises KeyError, TypeError or ValueError if the stored form is not valid.
    """
    on_timer, off_timer = stored["on_timer"], stored["off_timer"]
    return DaikinAcState(
        power=bool(stored["power"]),
        mode=DaikinAcMode[stored["mode"]],
        temperature=stored["temperature"],
        fan=DaikinAcFanSpeed[stored["fan"]],
        swing_v=bool(stored["swing_v"]),
        swing_h=bool(stored["swing_h"]),
        powerful=bool(stored["powerful"]),
        econo=bool(stored["econo"]),
        quiet=bool(stored["quiet"]),
        sensor=bool(stored["sensor"]),
        on_timer=time.fromisoformat(on_timer) if on_timer else None,
        off_timer=time.fromisoformat(off_timer) if off_timer else None,
        weekly_timer=bool(stored["weekly_timer"]),
    )


@dataclass
class _DaikinAcExtraStoredData(ExtraStoredData):
    """The full unit state, including what the entity does not show.

    The next command resends all of it, so settings made on the physical remote,
    like its timers, survive a restart instead of being cancelled.
    """

    state: DaikinAcState
    comfort: DaikinAcComfort
    setpoints: dict[DaikinAcMode, float]

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored data."""
        return {
            "state": _state_as_dict(self.state),
            "comfort": {
                "comfort": self.comfort.comfort,
                "brightness": self.comfort.brightness.name,
            },
            "setpoints": {mode.name: value for mode, value in self.setpoints.items()},
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize the stored data from a dict, or None if it is not valid."""
        try:
            return cls(
                state=_state_from_dict(restored["state"]),
                comfort=DaikinAcComfort(
                    comfort=bool(restored["comfort"]["comfort"]),
                    brightness=DaikinAcBrightness[restored["comfort"]["brightness"]],
                ),
                setpoints={
                    DaikinAcMode[mode]: float(value)
                    for mode, value in restored["setpoints"].items()
                },
            )
        except KeyError, TypeError, ValueError:
            return None


def _disable_powerful_on_off(state: DaikinAcState) -> DaikinAcState:
    """Return the state with powerful cleared while off.

    The unit leaves powerful mode when it is turned off, and the remote sends the off
    frame without it.
    """
    if state.power:
        return state
    return replace(state, powerful=False)


def _clock(now: datetime) -> DaikinAcClock:
    """Return the clock frame for the current local time."""
    return DaikinAcClock(time_of_day=now.time(), weekday=Day(now.weekday()))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Daikin AC climate entity from a config entry."""
    emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            [DaikinAcClimateWithReceiver(entry, emitter_entity_id, receiver_entity_id)]
        )
    else:
        async_add_entities([DaikinAcClimate(entry, emitter_entity_id)])


class DaikinAcClimate(InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity):
    """Daikin AC climate entity controlled through an infrared emitter.

    Every transmission carries the whole state, so the entity keeps the state the
    unit last got and derives what it shows from it.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "daikin_ac"
    _attr_assumed_state = True
    _attr_should_poll = False
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, *_HA_MODE_TO_LIB]
    _attr_fan_modes = list(_HA_FAN_TO_LIB)
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_swing_horizontal_modes = [SWING_OFF, SWING_ON]
    _attr_preset_modes = [PRESET_NONE, PRESET_ECO, PRESET_BOOST]

    def __init__(self, entry: ConfigEntry, emitter_entity_id: str) -> None:
        """Initialize the Daikin AC climate entity."""
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Daikin AC",
            manufacturer="Daikin",
        )
        self._infrared_emitter_entity_id = emitter_entity_id
        self._ac_state = DaikinAcState(
            power=False, mode=DaikinAcMode.COOL, temperature=DEFAULT_TEMPERATURE
        )
        self._comfort = DaikinAcComfort()
        self._setpoints: dict[DaikinAcMode, float] = {}
        self._cancel_boost: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the state the unit was last sent, as infrared cannot read it."""
        await super().async_added_to_hass()
        self.async_on_remove(self._async_cancel_boost)
        if (last_extra_data := await self.async_get_last_extra_data()) is None or (
            stored := _DaikinAcExtraStoredData.from_dict(last_extra_data.as_dict())
        ) is None:
            return
        # How long the unit has been in powerful mode is not known after a restart.
        self._ac_state = replace(stored.state, powerful=False)
        self._comfort = stored.comfort
        self._setpoints = stored.setpoints

    @property
    @override
    def extra_restore_state_data(self) -> _DaikinAcExtraStoredData:
        """Return the full unit state to be restored."""
        return _DaikinAcExtraStoredData(
            state=self._ac_state, comfort=self._comfort, setpoints=self._setpoints
        )

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the supported features; dry and fan only have no setpoint."""
        features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.SWING_HORIZONTAL_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self._ac_state.mode in TEMPERATURE_RANGES:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        return features

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if not self._ac_state.power:
            return HVACMode.OFF
        return _LIB_MODE_TO_HA[self._ac_state.mode]

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the setpoint of the current mode."""
        return self._ac_state.temperature

    @property
    @override
    def min_temp(self) -> float:
        """Return the lowest setpoint of the current mode."""
        return TEMPERATURE_RANGES.get(self._ac_state.mode, _FULL_RANGE).low

    @property
    @override
    def max_temp(self) -> float:
        """Return the highest setpoint of the current mode."""
        return TEMPERATURE_RANGES.get(self._ac_state.mode, _FULL_RANGE).high

    @property
    @override
    def fan_mode(self) -> str:
        """Return the fan speed."""
        return _LIB_FAN_TO_HA[self._ac_state.fan]

    @property
    @override
    def swing_mode(self) -> str:
        """Return whether the vanes swing vertically."""
        return SWING_ON if self._ac_state.swing_v else SWING_OFF

    @property
    @override
    def swing_horizontal_mode(self) -> str:
        """Return whether the vanes swing horizontally."""
        return SWING_ON if self._ac_state.swing_h else SWING_OFF

    @property
    @override
    def preset_mode(self) -> str:
        """Return the preset; powerful and econo exclude each other on the unit."""
        if self._ac_state.powerful:
            return PRESET_BOOST
        if self._ac_state.econo:
            return PRESET_ECO
        return PRESET_NONE

    def _in_mode(self, state: DaikinAcState, mode: DaikinAcMode) -> DaikinAcState:
        """Return the state switched to a mode, with that mode's own setpoint."""
        if mode not in TEMPERATURE_RANGES:
            return replace(state, mode=mode, temperature=None)
        low, high = TEMPERATURE_RANGES[mode]
        temperature = self._setpoints.get(
            mode, state.temperature or DEFAULT_TEMPERATURE
        )
        return replace(state, mode=mode, temperature=min(max(temperature, low), high))

    @callback
    def _async_set_ac_state(self, state: DaikinAcState) -> None:
        """Record the state the unit now has."""
        state = _disable_powerful_on_off(state)
        if state.temperature is not None:
            self._setpoints[state.mode] = state.temperature
        if state.powerful and not self._ac_state.powerful:
            self._async_cancel_boost()
            self._cancel_boost = async_call_later(
                self.hass, BOOST_DURATION, self._async_boost_ended
            )
        elif not state.powerful:
            self._async_cancel_boost()
        self._ac_state = state

    @callback
    def _async_cancel_boost(self) -> None:
        """Cancel the timer that ends powerful mode."""
        if self._cancel_boost is not None:
            self._cancel_boost()
            self._cancel_boost = None

    @callback
    def _async_boost_ended(self, _now: datetime) -> None:
        """Mirror the unit leaving powerful mode by itself."""
        self._cancel_boost = None
        self._ac_state = replace(self._ac_state, powerful=False)
        self.async_write_ha_state()

    async def _async_send(self, state: DaikinAcState) -> None:
        """Send a transmission carrying the given state."""
        state = _disable_powerful_on_off(state)
        await self._send_command(
            DaikinAcCommand(
                state=state, comfort=self._comfort, clock=_clock(dt_util.now())
            )
        )
        self._async_set_ac_state(state)
        self.async_write_ha_state()

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode is HVACMode.OFF:
            await self._async_send(replace(self._ac_state, power=False))
            return
        state = self._in_mode(self._ac_state, _HA_MODE_TO_LIB[hvac_mode])
        await self._async_send(replace(state, power=True))

    @override
    async def async_turn_on(self) -> None:
        """Turn the unit on in the mode it was last in."""
        await self._async_send(replace(self._ac_state, power=True))

    @override
    async def async_turn_off(self) -> None:
        """Turn the unit off, keeping its mode for the next time it is on."""
        await self._async_send(replace(self._ac_state, power=False))

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the setpoint, switching the HVAC mode first when one is given."""
        state = self._ac_state
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)
            if hvac_mode is HVACMode.OFF:
                state = replace(state, power=False)
            else:
                state = replace(
                    self._in_mode(state, _HA_MODE_TO_LIB[hvac_mode]), power=True
                )
        if state.mode in TEMPERATURE_RANGES:
            low, high = TEMPERATURE_RANGES[state.mode]
            # Although the step is 1.0, converting from °F is more precise
            # when using half degrees, which the protocol supports
            temperature = round(kwargs[ATTR_TEMPERATURE] * 2) / 2
            state = replace(state, temperature=min(max(temperature, low), high))
        await self._async_send(state)

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        await self._async_send(replace(self._ac_state, fan=_HA_FAN_TO_LIB[fan_mode]))

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set whether the vanes swing vertically."""
        await self._async_send(replace(self._ac_state, swing_v=swing_mode == SWING_ON))

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set whether the vanes swing horizontally."""
        await self._async_send(
            replace(self._ac_state, swing_h=swing_horizontal_mode == SWING_ON)
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset; powerful clears econo and quiet, as the remote does."""
        powerful = preset_mode == PRESET_BOOST
        state = replace(
            self._ac_state,
            powerful=powerful,
            econo=preset_mode == PRESET_ECO,
            quiet=self._ac_state.quiet and not powerful,
        )
        await self._async_send(state)


class DaikinAcClimateWithReceiver(DaikinAcClimate, InfraredReceiverConsumerEntity):
    """Daikin AC climate entity that also follows the physical remote."""

    def __init__(
        self, entry: ConfigEntry, emitter_entity_id: str, receiver_entity_id: str
    ) -> None:
        """Initialize the Daikin AC climate entity with a receiver."""
        super().__init__(entry, emitter_entity_id)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update the state from what the physical remote sent.

        A signal holds one frame or a whole transmission, depending on how long the
        receiver waits before ending a capture, so each part is applied on its own.
        """
        if (command := DaikinAcCommand.from_raw_timings(signal.timings)) is None:
            return
        if command.comfort is not None:
            self._comfort = command.comfort
        if command.state is not None:
            self._async_set_ac_state(command.state)
            self.async_write_ha_state()
