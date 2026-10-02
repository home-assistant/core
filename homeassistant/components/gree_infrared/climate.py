"""Climate platform for Gree IR integration — Gree AC."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, override

from infrared_protocols.commands.gree_ac import (
    _YAP1F_SWING_POSITIONS,
    MAX_TEMP,
    MIN_TEMP,
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcFreshAir,
    GreeAcMode,
    GreeAcModel,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
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
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from . import GreeInfraredConfigEntry
from .const import (
    CONF_GENERIC_OPTIONS,
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_MODEL,
    MODEL_GENERIC,
    MODEL_YAP1F,
)
from .entity import GreeIrEntity
from .state import GreeAcState

PARALLEL_UPDATES = 1

_HA_FAN_TO_LIB: dict[str, GreeAcFanSpeed] = {
    FAN_AUTO: GreeAcFanSpeed.AUTO,
    FAN_LOW: GreeAcFanSpeed.LOW,
    FAN_MEDIUM: GreeAcFanSpeed.MEDIUM,
    FAN_HIGH: GreeAcFanSpeed.HIGH,
}
_LIB_FAN_TO_HA: dict[GreeAcFanSpeed, str] = {v: k for k, v in _HA_FAN_TO_LIB.items()}

# Every mode other than OFF; the protocol has no OFF mode of its own, power is a
# separate field, so this dict intentionally has no HVACMode.OFF entry.
_HA_MODE_TO_LIB: dict[HVACMode, GreeAcMode] = {
    HVACMode.AUTO: GreeAcMode.AUTO,
    HVACMode.COOL: GreeAcMode.COOL,
    HVACMode.HEAT: GreeAcMode.HEAT,
    HVACMode.DRY: GreeAcMode.DRY,
    HVACMode.FAN_ONLY: GreeAcMode.FAN_ONLY,
}
_LIB_MODE_TO_HA: dict[GreeAcMode, HVACMode] = {v: k for k, v in _HA_MODE_TO_LIB.items()}

_HA_FRESH_AIR_TO_LIB: dict[str, GreeAcFreshAir] = {
    "off": GreeAcFreshAir.OFF,
    "level_1": GreeAcFreshAir.LEVEL_1,
    "level_2": GreeAcFreshAir.LEVEL_2,
}
_LIB_FRESH_AIR_TO_HA: dict[GreeAcFreshAir, str] = {
    v: k for k, v in _HA_FRESH_AIR_TO_LIB.items()
}
FRESH_AIR_OPTIONS = list(_HA_FRESH_AIR_TO_LIB)

VANE_AUTO = "auto"
VANE_OPTIONS = [VANE_AUTO, *(str(p) for p in _YAP1F_SWING_POSITIONS)]
HORIZONTAL_POSITION_OPTIONS = [
    "off",
    "auto",
    "max_left",
    "left",
    "middle",
    "right",
    "max_right",
]
DISPLAY_TEMP_OPTIONS = ["off", "setpoint", "indoor", "outdoor"]

# The YAP1F remote cancels sleep when the mode changes or the unit is turned
# off, and sleep cannot be enabled in auto or fan-only modes.
SLEEP_BLOCKED_HVAC_MODES = (HVACMode.AUTO, HVACMode.FAN_ONLY)


@dataclass
class _GreeAcExtraStoredData(ExtraStoredData):
    """Extra data restored alongside the entity's visible state."""

    last_active_hvac_mode: str
    turbo: bool = False
    light: bool = True
    health: bool = False
    xfan: bool = False
    sleep: bool = False
    ifeel: bool = False
    swing_v: bool = False
    swing_h: bool = False
    swing_v_position: int | None = None
    fresh_air: int = int(GreeAcFreshAir.OFF)
    timer_hours: float | None = None
    timer_deadline: str | None = None
    swing_h_position: int = 0
    econo: bool = False
    absence: bool = False
    fahrenheit: bool = False
    display_temp: int = 2

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation for storage."""
        return {
            "last_active_hvac_mode": self.last_active_hvac_mode,
            "turbo": self.turbo,
            "light": self.light,
            "health": self.health,
            "xfan": self.xfan,
            "sleep": self.sleep,
            "ifeel": self.ifeel,
            "swing_v": self.swing_v,
            "swing_h": self.swing_h,
            "swing_v_position": self.swing_v_position,
            "fresh_air": self.fresh_air,
            "timer_hours": self.timer_hours,
            "timer_deadline": self.timer_deadline,
            "swing_h_position": self.swing_h_position,
            "econo": self.econo,
            "absence": self.absence,
            "fahrenheit": self.fahrenheit,
            "display_temp": self.display_temp,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> _GreeAcExtraStoredData | None:
        """Build from a stored dict, or None if it doesn't look valid."""
        last_active_hvac_mode = restored.get("last_active_hvac_mode")
        if not isinstance(last_active_hvac_mode, str):
            return None
        flags = tuple(
            restored.get(key, default)
            for key, default in (
                ("turbo", False),
                ("light", True),
                ("health", False),
                ("xfan", False),
                ("sleep", False),
                ("ifeel", False),
                ("swing_v", False),
                ("swing_h", False),
            )
        )
        if any(not isinstance(flag, bool) for flag in flags):
            return None
        swing_v_position = restored.get("swing_v_position")
        if swing_v_position is not None and (
            not isinstance(swing_v_position, int)
            or swing_v_position not in _YAP1F_SWING_POSITIONS
        ):
            return None
        fresh_air = restored.get("fresh_air", int(GreeAcFreshAir.OFF))
        if fresh_air not in tuple(int(v) for v in GreeAcFreshAir):
            return None
        timer_hours = restored.get("timer_hours")
        if timer_hours is not None and (
            not isinstance(timer_hours, (int, float))
            or not 0.5 <= float(timer_hours) <= 24
            or (float(timer_hours) * 2) % 1
        ):
            return None
        timer_deadline = restored.get("timer_deadline")
        if timer_deadline is not None and (
            not isinstance(timer_deadline, str)
            or dt_util.parse_datetime(timer_deadline) is None
        ):
            return None
        swing_h_position = restored.get("swing_h_position", 0)
        econo = restored.get("econo", False)
        absence = restored.get("absence", False)
        fahrenheit = restored.get("fahrenheit", False)
        display_temp = restored.get("display_temp", 2)
        if (
            not isinstance(swing_h_position, int)
            or swing_h_position not in range(7)
            or not isinstance(econo, bool)
            or not isinstance(absence, bool)
            or not isinstance(fahrenheit, bool)
            or not isinstance(display_temp, int)
            or display_temp not in range(4)
        ):
            return None
        return cls(
            last_active_hvac_mode,
            *flags,
            swing_v_position,
            int(fresh_air),
            None if timer_hours is None else float(timer_hours),
            timer_deadline,
            swing_h_position,
            econo,
            absence,
            fahrenheit,
            display_temp,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeInfraredConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gree AC climate entity from config entry."""
    emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    model = entry.data.get(CONF_MODEL, MODEL_GENERIC)
    state = entry.runtime_data
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            [
                GreeAcClimateWithReceiver(
                    entry, emitter_entity_id, receiver_entity_id, model, state
                )
            ]
        )
    else:
        async_add_entities(
            [GreeAcClimateEntity(entry, emitter_entity_id, model, state)]
        )


class GreeAcClimateEntity(
    GreeIrEntity, InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity
):
    """Gree AC climate entity controlled via infrared emitter."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = float(MIN_TEMP)
    _attr_max_temp = float(MAX_TEMP)
    _attr_should_poll = False
    _attr_assumed_state = True
    # Every mode's frame carries a temperature and a fan field, so both features are
    # always supported regardless of which modes are configured. Swing axes are
    # separate block-B bits, so both swing features are always supported too.
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
    )
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_swing_horizontal_modes = [SWING_OFF, SWING_ON]

    def __init__(
        self, entry: ConfigEntry, emitter_entity_id: str, model: str, state: GreeAcState
    ) -> None:
        """Initialize Gree AC climate entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = emitter_entity_id
        self._state = state
        self._generic_options = entry.data.get(CONF_GENERIC_OPTIONS, False)
        self._model = GreeAcModel.YAP1F if model == MODEL_YAP1F else GreeAcModel.GENERIC
        configured_modes = entry.data.get(
            CONF_HVAC_MODES, [HVACMode.COOL, HVACMode.DRY]
        )
        self._attr_hvac_modes = [HVACMode.OFF] + [HVACMode(m) for m in configured_modes]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(MIN_TEMP)
        self._attr_fan_mode = FAN_AUTO
        self._attr_swing_mode = SWING_OFF
        self._attr_swing_horizontal_mode = SWING_OFF
        # Power-off frames still need a mode field; this tracks the mode to send it
        # with, since the protocol has no dedicated OFF mode.
        self._last_active_hvac_mode = self._attr_hvac_modes[1]
        self._timer_deadline: datetime | None = None
        self._state.climate = self

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clear the shared climate owner on unload."""
        await super().async_will_remove_from_hass()
        if self._state.climate is self:
            self._state.climate = None
            self._state.async_notify_switches()

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()

        @callback
        def _handle_climate_state_change(
            event: Event[EventStateChangedData],
        ) -> None:
            self._state.async_notify_switches()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.entity_id], _handle_climate_state_change
            )
        )
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            if last_state.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(last_state.state)
            if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in _HA_FAN_TO_LIB:
                self._attr_fan_mode = fan_mode
            if (swing_mode := last_state.attributes.get(ATTR_SWING_MODE)) in (
                SWING_OFF,
                SWING_ON,
            ):
                self._state.swing_v = swing_mode == SWING_ON
                self._attr_swing_mode = swing_mode
            if (swing_h_mode := last_state.attributes.get("swing_horizontal_mode")) in (
                SWING_OFF,
                SWING_ON,
            ):
                self._state.swing_h = swing_h_mode == SWING_ON
                self._attr_swing_horizontal_mode = swing_h_mode
            if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(
                    round(
                        TemperatureConverter.convert(
                            float(temperature),
                            self.hass.config.units.temperature_unit,
                            self.temperature_unit,
                        )
                    )
                )

        current_mode = self._attr_hvac_mode
        last_extra_data = await self.async_get_last_extra_data()
        restored = (
            _GreeAcExtraStoredData.from_dict(last_extra_data.as_dict())
            if last_extra_data is not None
            else None
        )
        if current_mode is not None and current_mode is not HVACMode.OFF:
            self._last_active_hvac_mode = current_mode
        elif restored is not None and restored.last_active_hvac_mode in (
            mode.value for mode in self._attr_hvac_modes if mode is not HVACMode.OFF
        ):
            self._last_active_hvac_mode = HVACMode(restored.last_active_hvac_mode)
        if restored is not None:
            if self._supports_options:
                self._state.turbo = restored.turbo
                self._state.light = restored.light
                self._state.health = restored.health
                self._state.xfan = restored.xfan
            # The generic frame carries swing, sleep, fresh-air and timer bits, so
            # these restore on both profiles. IFeel and the fixed vane position are
            # YAP1F-only fields; drop them for generic instead of sending a value
            # the generic profile cannot encode.
            self._state.swing_v = restored.swing_v
            self._state.swing_h = restored.swing_h
            self._state.sleep = restored.sleep
            self._state.fresh_air = restored.fresh_air
            self._state.timer_hours = restored.timer_hours
            self._timer_deadline = (
                dt_util.as_utc(dt_util.parse_datetime(restored.timer_deadline))
                if restored.timer_deadline is not None
                else dt_util.utcnow() + timedelta(hours=restored.timer_hours)
                if restored.timer_hours is not None
                else None
            )
            if self._is_yap1f:
                self._state.ifeel = restored.ifeel
                self._state.swing_v_position = restored.swing_v_position
            else:
                self._state.ifeel = False
                self._state.swing_v_position = None
            self._attr_swing_mode = SWING_ON if self._state.swing_v else SWING_OFF
            self._attr_swing_horizontal_mode = (
                SWING_ON if self._state.swing_h else SWING_OFF
            )
            if self._attr_hvac_mode in SLEEP_BLOCKED_HVAC_MODES:
                # Sleep cannot exist in auto/fan-only; drop a stale restored value.
                # A stored value while OFF is kept like the other assumed options
                # and is cancelled by the next mode change or power-off send.
                self._state.sleep = False
            self._state.swing_h_position = restored.swing_h_position
            self._state.econo = restored.econo
            self._state.absence = restored.absence
            self._state.fahrenheit = restored.fahrenheit
            self._state.display_temp = restored.display_temp
        self._state.async_notify_switches()

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return extra data to be restored alongside the entity's state."""
        return _GreeAcExtraStoredData(
            self._last_active_hvac_mode.value,
            self._state.turbo,
            self._state.light,
            self._state.health,
            self._state.xfan,
            self._state.sleep,
            self._state.ifeel,
            self._state.swing_v,
            self._state.swing_h,
            self._state.swing_v_position,
            self._state.fresh_air,
            self._state.timer_hours,
            self._timer_deadline.isoformat() if self._timer_deadline else None,
            self._state.swing_h_position,
            self._state.econo,
            self._state.absence,
            self._state.fahrenheit,
            self._state.display_temp,
        )

    def _remaining_timer_hours(self) -> float | None:
        """Return the active timer rounded to the protocol's half-hour step."""
        if self._timer_deadline is None:
            return self._state.timer_hours
        remaining = (self._timer_deadline - dt_util.utcnow()).total_seconds() / 3600
        if remaining <= 0:
            self._timer_deadline = None
            self._state.timer_hours = None
            return None
        return max(0.5, int(remaining * 2 + 0.5) / 2)

    async def _async_send_state(
        self, hvac_mode: HVACMode, temp: int, fan_mode: str
    ) -> None:
        """Send a full-state frame for the given target state."""
        power = hvac_mode is not HVACMode.OFF
        active_hvac_mode = hvac_mode if power else self._last_active_hvac_mode
        await self._send_command(
            self._build_command(active_hvac_mode, power, temp, fan_mode)
        )
        if power:
            self._last_active_hvac_mode = hvac_mode

    def _clear_sleep_on_mode_change(self, new_hvac_mode: HVACMode) -> dict[str, bool]:
        """Cancel sleep when the mode changes or the unit turns off.

        The remote clears sleep on any mode change and on power-off, so the
        assumed state follows the same rule before building the next frame.
        The previous value of each cancelled option is returned so the caller
        can restore them when the frame never goes out; the switches are
        notified only once the send has succeeded.
        """
        cleared: dict[str, bool] = {}
        if (
            new_hvac_mode is HVACMode.OFF
            or new_hvac_mode != self._last_active_hvac_mode
        ) and self._state.sleep:
            cleared["sleep"] = self._state.sleep
            self._state.sleep = False
        if new_hvac_mode is not HVACMode.COOL and self._state.econo:
            cleared["econo"] = self._state.econo
            self._state.econo = False
        if new_hvac_mode is not HVACMode.HEAT and self._state.absence:
            cleared["absence"] = self._state.absence
            self._state.absence = False
        return cleared

    async def async_set_option(self, option: str, value: bool) -> None:
        """Set an option flag and send the updated state when active."""
        if option in ("turbo", "light", "health", "xfan"):
            if not self._supports_options:
                raise ValueError(f"Unsupported Gree option: {option}")
        elif option == "sleep":
            pass
        elif option in ("ifeel", "econo", "absence"):
            if not self._is_yap1f:
                raise ValueError(f"Unsupported Gree option: {option}")
        else:
            raise ValueError(f"Unsupported Gree option: {option}")
        if (
            option == "sleep"
            and value
            and self._attr_hvac_mode
            in (
                *SLEEP_BLOCKED_HVAC_MODES,
                HVACMode.OFF,
            )
        ):
            raise HomeAssistantError("Sleep is not available in this HVAC mode")
        if option == "econo" and value and self._attr_hvac_mode is not HVACMode.COOL:
            raise HomeAssistantError("Econo is only available in cool mode")
        if option == "absence" and value and self._attr_hvac_mode is not HVACMode.HEAT:
            raise HomeAssistantError("Absence is only available in heat mode")
        async with self._state.command_lock:
            previous = getattr(self._state, option)
            setattr(self._state, option, value)
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
            except Exception:
                setattr(self._state, option, previous)
                raise
            self._state.async_notify_switches()

    async def async_set_fresh_air(self, option: str) -> None:
        """Set the fresh-air intake level and send the updated state."""
        if option not in _HA_FRESH_AIR_TO_LIB:
            raise ValueError(f"Unsupported fresh-air option: {option}")
        async with self._state.command_lock:
            previous = self._state.fresh_air
            self._state.fresh_air = int(_HA_FRESH_AIR_TO_LIB[option])
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
            except Exception:
                self._state.fresh_air = previous
                raise
            self._state.async_notify_switches()

    async def async_set_timer_hours(self, timer_hours: float | None) -> None:
        """Set the countdown timer (None = off) and send the updated state."""
        if timer_hours is not None and (
            not 0.5 <= timer_hours <= 24 or (timer_hours * 2) % 1
        ):
            raise ValueError(f"Unsupported timer value: {timer_hours}")
        async with self._state.command_lock:
            previous = self._state.timer_hours
            previous_deadline = self._timer_deadline
            self._state.timer_hours = timer_hours
            self._timer_deadline = (
                dt_util.utcnow() + timedelta(hours=timer_hours)
                if timer_hours is not None
                else None
            )
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
            except Exception:
                self._state.timer_hours = previous
                self._timer_deadline = previous_deadline
                raise
            self._state.async_notify_switches()

    async def async_set_swing_v_position(self, position: int | None) -> None:
        """Set the fixed vertical vane position (None = follow sweep).

        Fixed positions are exposed on a select rather than overloading the
        binary climate swing_mode: sweep stays a native off/on swing while the
        ten discrete YAP1F positions need string options the climate service
        cannot validate. Selecting a fixed position parks the vane there;
        selecting auto returns to sweep control.
        """
        if not self._is_yap1f:
            raise ValueError("Vane position is only available on the YAP1F model")
        if position is not None and position not in _YAP1F_SWING_POSITIONS:
            raise ValueError(f"Unsupported vane position: {position}")
        async with self._state.command_lock:
            previous_position = self._state.swing_v_position
            previous_swing_v = self._state.swing_v
            if position is None:
                self._state.swing_v_position = None
            else:
                self._state.swing_v_position = position
                self._state.swing_v = False
                self._attr_swing_mode = SWING_OFF
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
                self.async_write_ha_state()
            except Exception:
                self._state.swing_v_position = previous_position
                self._state.swing_v = previous_swing_v
                self._attr_swing_mode = SWING_ON if previous_swing_v else SWING_OFF
                raise
            self._state.async_notify_switches()

    @property
    def _supports_options(self) -> bool:
        """Return whether this profile exposes the shared option flags."""
        return self._model is GreeAcModel.YAP1F or self._generic_options

    @property
    def _is_yap1f(self) -> bool:
        """Return whether the YAP1F wire profile is selected."""
        return self._model is GreeAcModel.YAP1F

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        async with self._state.command_lock:
            cleared = self._clear_sleep_on_mode_change(hvac_mode)
            try:
                await self._async_send_state(
                    hvac_mode,
                    int(self._attr_target_temperature or MIN_TEMP),
                    self._attr_fan_mode or FAN_AUTO,
                )
            except Exception:
                for option, value in cleared.items():
                    setattr(self._state, option, value)
                raise
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()
            self._state.async_notify_switches()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, switching the HVAC mode when one is given."""
        async with self._state.command_lock:
            temp = round(kwargs[ATTR_TEMPERATURE])
            hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
            cleared: dict[str, bool] = {}
            if hvac_mode is not None:
                self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)
                cleared = self._clear_sleep_on_mode_change(hvac_mode)
            effective_mode = hvac_mode or self._attr_hvac_mode or HVACMode.OFF
            if effective_mode is not HVACMode.OFF or hvac_mode is HVACMode.OFF:
                try:
                    await self._async_send_state(
                        effective_mode,
                        temp,
                        self._attr_fan_mode or FAN_AUTO,
                    )
                except Exception:
                    for option, value in cleared.items():
                        setattr(self._state, option, value)
                    raise
            if hvac_mode is not None:
                self._attr_hvac_mode = hvac_mode
            self._attr_target_temperature = float(temp)
            self.async_write_ha_state()
            self._state.async_notify_switches()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        async with self._state.command_lock:
            hvac_mode = self._attr_hvac_mode
            if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                await self._async_send_state(
                    hvac_mode, int(self._attr_target_temperature or MIN_TEMP), fan_mode
                )
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set vertical sweep."""
        self._valid_mode_or_raise("swing", swing_mode, self.swing_modes)
        async with self._state.command_lock:
            previous = self._state.swing_v
            previous_position = self._state.swing_v_position
            self._state.swing_v = swing_mode == SWING_ON
            # Sweep and fixed positions share the YAP1F low nibble, so an
            # explicit sweep choice returns to follow mode.
            self._state.swing_v_position = None
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
                self._attr_swing_mode = swing_mode
                self.async_write_ha_state()
            except Exception:
                self._state.swing_v = previous
                self._state.swing_v_position = previous_position
                raise
            self._state.async_notify_switches()

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set horizontal sweep."""
        self._valid_mode_or_raise(
            "horizontal swing", swing_horizontal_mode, self.swing_horizontal_modes
        )
        async with self._state.command_lock:
            previous = self._state.swing_h
            previous_position = self._state.swing_h_position
            self._state.swing_h = swing_horizontal_mode == SWING_ON
            self._state.swing_h_position = int(self._state.swing_h)
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
                self._attr_swing_horizontal_mode = swing_horizontal_mode
                self.async_write_ha_state()
            except Exception:
                self._state.swing_h = previous
                self._state.swing_h_position = previous_position
                raise
            self._state.async_notify_switches()

    async def async_set_swing_h_position(self, position: int) -> None:
        """Set a fixed horizontal vane position, with zero following sweep."""
        if position not in range(7):
            raise ValueError(f"Unsupported horizontal vane position: {position}")
        async with self._state.command_lock:
            previous_position = self._state.swing_h_position
            previous_swing = self._state.swing_h
            self._state.swing_h_position = position
            self._state.swing_h = position != 0
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
                self._attr_swing_horizontal_mode = SWING_ON if position else SWING_OFF
                self.async_write_ha_state()
            except Exception:
                self._state.swing_h_position = previous_position
                self._state.swing_h = previous_swing
                raise
            self._state.async_notify_switches()

    async def async_set_display_temp(self, display_temp: int) -> None:
        """Select the temperature shown on the unit display."""
        if display_temp not in range(4):
            raise ValueError(f"Unsupported display temperature: {display_temp}")
        await self._async_set_yap1f_field("display_temp", display_temp)

    async def async_set_fahrenheit(self, fahrenheit: bool) -> None:
        """Select the unit display scale independent of HA's climate unit."""
        await self._async_set_yap1f_field("fahrenheit", fahrenheit)

    async def _async_set_yap1f_field(self, key: str, value: Any) -> None:
        """Set and send one YAP1F command field."""
        if not self._is_yap1f:
            raise ValueError(f"{key} is only available on the YAP1F model")
        async with self._state.command_lock:
            previous = getattr(self._state, key)
            setattr(self._state, key, value)
            try:
                hvac_mode = self._attr_hvac_mode
                if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                    await self._async_send_state(
                        hvac_mode,
                        int(self._attr_target_temperature or MIN_TEMP),
                        self._attr_fan_mode or FAN_AUTO,
                    )
            except Exception:
                setattr(self._state, key, previous)
                raise
            self._state.async_notify_switches()

    def _build_command(
        self, hvac_mode: HVACMode, power: bool, temp: int, fan_mode: str
    ) -> GreeAcCommand:
        """Build a command from a mode, power state, a temperature and a fan mode."""
        if self._is_yap1f and self._state.fahrenheit:
            temp = round(
                TemperatureConverter.convert(
                    temp,
                    UnitOfTemperature.CELSIUS,
                    UnitOfTemperature.FAHRENHEIT,
                )
            )
        return GreeAcCommand(
            model=self._model,
            power=power,
            mode=_HA_MODE_TO_LIB[hvac_mode],
            temperature=temp,
            fan=_HA_FAN_TO_LIB[fan_mode],
            swing_v=self._state.swing_v,
            swing_h=self._state.swing_h,
            turbo=self._state.turbo,
            display=self._state.light,
            anion=self._state.health,
            blow=self._state.xfan,
            sleep=self._state.sleep,
            timer_hours=self._remaining_timer_hours(),
            fresh_air=GreeAcFreshAir(self._state.fresh_air),
            ifeel=self._state.ifeel if self._is_yap1f else False,
            swing_v_position=self._state.swing_v_position if self._is_yap1f else None,
            swing_h_position=(
                self._state.swing_h_position
                if self._is_yap1f
                else int(self._state.swing_h)
            ),
            fahrenheit=self._state.fahrenheit if self._is_yap1f else False,
            econo=self._state.econo if self._is_yap1f else False,
            absence=self._state.absence if self._is_yap1f else False,
            display_temp=self._state.display_temp if self._is_yap1f else None,
        )


class GreeAcClimateWithReceiver(GreeAcClimateEntity, InfraredReceiverConsumerEntity):
    """Gree AC climate entity that also tracks a configured infrared receiver."""

    def __init__(
        self,
        entry: ConfigEntry,
        emitter_entity_id: str,
        receiver_entity_id: str,
        model: str,
        state: GreeAcState,
    ) -> None:
        """Initialize Gree AC climate entity with a receiver."""
        super().__init__(entry, emitter_entity_id, model, state)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Schedule received-state updates behind any in-flight send."""
        self.hass.async_create_task(self._async_handle_signal(signal))

    async def _async_handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal under the command lock."""
        async with self._state.command_lock:
            self._handle_signal_locked(signal)

    def _handle_signal_locked(self, signal: InfraredReceivedSignal) -> None:
        """Apply a received physical remote signal."""
        command = GreeAcCommand.from_raw_timings(signal.timings, model=self._model)
        if command is None:
            return
        if self._model is GreeAcModel.GENERIC and (
            GreeAcCommand.from_raw_timings(signal.timings, model=GreeAcModel.YAP1F)
            is not None
        ):
            # A YAP1F remote's first frame is generic-shaped; only the selected
            # profile may claim the two-frame signal.
            return

        # Off frames carry a mode field too, so the mode is recorded either way.
        embedded_hvac_mode = _LIB_MODE_TO_HA[command.mode]
        if embedded_hvac_mode in self._attr_hvac_modes:
            self._last_active_hvac_mode = embedded_hvac_mode
        elif command.power:
            return

        self._attr_hvac_mode = embedded_hvac_mode if command.power else HVACMode.OFF
        self._attr_fan_mode = _LIB_FAN_TO_HA[command.fan]
        temperature = command.temperature
        if command.fahrenheit:
            # The decoded value is the display value; HA tracks the Celsius
            # target the wire field is derived from, keeping the decoded scale
            # so the next frame converts back the same way.
            temperature = round(
                TemperatureConverter.convert(
                    temperature,
                    UnitOfTemperature.FAHRENHEIT,
                    UnitOfTemperature.CELSIUS,
                )
            )
        self._attr_target_temperature = float(temperature)
        self._state.fahrenheit = command.fahrenheit
        self._state.swing_v = command.swing_v
        self._state.swing_h = command.swing_h
        self._attr_swing_mode = SWING_ON if command.swing_v else SWING_OFF
        self._attr_swing_horizontal_mode = SWING_ON if command.swing_h else SWING_OFF
        self._state.sleep = command.sleep
        if self._attr_hvac_mode in (*SLEEP_BLOCKED_HVAC_MODES, HVACMode.OFF):
            self._state.sleep = False
        self._state.fresh_air = int(command.fresh_air)
        self._state.timer_hours = command.timer_hours
        self._timer_deadline = (
            dt_util.utcnow() + timedelta(hours=command.timer_hours)
            if command.timer_hours is not None
            else None
        )
        if self._is_yap1f:
            self._state.ifeel = command.ifeel
            self._state.swing_v_position = command.swing_v_position
            self._state.swing_h_position = command.swing_h_position
            self._state.display_temp = command.display_temp
            # Byte 7 0x04 is econo in cool and absence in heat; one wire bit.
            self._state.econo = command.econo and embedded_hvac_mode is HVACMode.COOL
            self._state.absence = (
                command.absence and embedded_hvac_mode is HVACMode.HEAT
            )
        if self._supports_options:
            self._state.turbo = command.turbo
            self._state.light = command.display
            self._state.health = command.anion
            self._state.xfan = command.blow
        self.async_write_ha_state()
        self._state.async_notify_switches()

    @override
    async def async_added_to_hass(self) -> None:
        """Restore receiver subscription alongside the assumed state."""
        await super().async_added_to_hass()
