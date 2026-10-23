"""Climate platform for Gree IR integration — Gree AC."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Self, override

from infrared_protocols.commands.gree_ac import (
    MAX_TEMP,
    MAX_TEMP_F,
    MIN_TEMP,
    MIN_TEMP_F,
    YAP1F_SWING_POSITIONS,
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
    ClimateEntityFeature,
    ClimateExtraStoredData,
    HVACMode,
    RestoreClimate,
)
from homeassistant.components.infrared import (
    InfraredEmitterConsumerEntity,
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_MODEL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from . import GreeInfraredConfigEntry
from .const import (
    CONF_GENERIC_OPTIONS,
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
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
VANE_OPTIONS = [VANE_AUTO, *(str(p) for p in YAP1F_SWING_POSITIONS)]
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

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class _GreeAcExtraStoredData(ClimateExtraStoredData):
    """Extra data restored alongside the entity's visible state.

    Holds the mode the unit was last actively in. The visible state only records
    OFF once the unit is off, but off frames still carry a mode field, so this
    cannot be recovered from last_state.state alone.
    """

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
    timer_expiry_power: bool | None = None
    swing_h_position: int = 0
    econo: bool = False
    absence: bool = False
    fahrenheit: bool = False
    display_temp: int = 2
    received_fahrenheit_temperature: int | None = None

    @classmethod
    @override
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize stored data from a dict."""
        climate_data = ClimateExtraStoredData.from_dict(restored)
        if climate_data is None:
            # Older Gree snapshots predate climate temperature fields. Those
            # values are restored from the entity state; keep the Gree options.
            climate_data = ClimateExtraStoredData(
                native_current_temperature=None,
                native_target_temperature=None,
                native_target_temperature_high=None,
                native_target_temperature_low=None,
                native_temperature_unit=UnitOfTemperature.CELSIUS.value,
            )
        if not isinstance(
            last_active_hvac_mode := restored.get("last_active_hvac_mode"), str
        ):
            return None
        flags = {
            key: restored.get(key, default)
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
        }
        if any(not isinstance(flag, bool) for flag in flags.values()):
            return None
        swing_v_position = restored.get("swing_v_position")
        if swing_v_position is not None and (
            not isinstance(swing_v_position, int)
            or swing_v_position not in YAP1F_SWING_POSITIONS
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
        timer_expiry_power = restored.get("timer_expiry_power")
        if timer_expiry_power is not None and not isinstance(timer_expiry_power, bool):
            return None
        swing_h_position = restored.get("swing_h_position", 0)
        econo = restored.get("econo", False)
        absence = restored.get("absence", False)
        fahrenheit = restored.get("fahrenheit", False)
        display_temp = restored.get("display_temp", 2)
        received_fahrenheit_temperature = restored.get(
            "received_fahrenheit_temperature"
        )
        if received_fahrenheit_temperature is not None and (
            not isinstance(received_fahrenheit_temperature, int)
            or received_fahrenheit_temperature not in range(MIN_TEMP_F, MAX_TEMP_F + 1)
        ):
            return None
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
            **climate_data.as_dict(),
            last_active_hvac_mode=last_active_hvac_mode,
            **flags,
            swing_v_position=swing_v_position,
            fresh_air=int(fresh_air),
            timer_hours=None if timer_hours is None else float(timer_hours),
            timer_deadline=timer_deadline,
            timer_expiry_power=timer_expiry_power,
            swing_h_position=swing_h_position,
            econo=econo,
            absence=absence,
            fahrenheit=fahrenheit,
            display_temp=display_temp,
            received_fahrenheit_temperature=received_fahrenheit_temperature,
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


class GreeAcClimateEntity(GreeIrEntity, InfraredEmitterConsumerEntity, RestoreClimate):
    """Gree AC climate entity controlled via infrared emitter."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
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
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
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
        self._attr_native_target_temperature = float(MIN_TEMP)
        self._received_fahrenheit_temperature: int | None = None
        self._attr_fan_mode = FAN_AUTO
        self._attr_swing_mode = SWING_OFF
        self._attr_swing_horizontal_mode = SWING_OFF
        # Power-off frames still need a mode field; this tracks the mode to send it
        # with, since the protocol has no dedicated OFF mode.
        self._last_active_hvac_mode = self._attr_hvac_modes[1]
        self._timer_deadline: datetime | None = None
        self._timer_expiry_power: bool | None = None
        self._timer_expiry_unsub: Callable[[], None] | None = None
        self._state.climate = self

    @override
    async def async_internal_will_remove_from_hass(self) -> None:
        """Drain staged commands before the restore snapshot is taken.

        The restore snapshot is cached before the removal hook runs, so the
        final frame must be transmitted first for the snapshot to hold the
        final deadline. Any expiry listener the flush schedules is dropped so
        no callback outlives the removed entity.
        """
        self._cancel_timer_expiry()
        await self._state.async_unload_coalesced_flush(self._async_flush_coalesced)
        self._cancel_timer_expiry()
        await super().async_internal_will_remove_from_hass()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Flush staged changes, then clear the shared climate owner."""
        await super().async_will_remove_from_hass()
        await self._state.async_unload_coalesced_flush(self._async_flush_coalesced)
        self._cancel_timer_expiry()
        if self._state.climate is self:
            self._state.climate = None
            self._state.async_notify_switches()

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()
        self._state.climate = self

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
            if (
                climate_data := await self.async_get_last_climate_data(
                    validate_range=True
                )
            ) is not None and (
                temperature := climate_data.native_target_temperature
            ) is not None:
                self._attr_native_target_temperature = float(round(temperature))

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
        elif (
            last_extra_data is not None
            and isinstance(
                last_active_hvac_mode := last_extra_data.as_dict().get(
                    "last_active_hvac_mode"
                ),
                str,
            )
            and last_active_hvac_mode
            in (
                mode.value for mode in self._attr_hvac_modes if mode is not HVACMode.OFF
            )
        ):
            # Saved before 2026.11 without the temperatures, remove in 2027.5
            self._last_active_hvac_mode = HVACMode(last_active_hvac_mode)
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
            self._timer_expiry_power = restored.timer_expiry_power
            self._timer_deadline = (
                (
                    dt_util.as_utc(parsed_timer_deadline)
                    if (
                        parsed_timer_deadline := dt_util.parse_datetime(
                            restored.timer_deadline
                        )
                    )
                    is not None
                    else None
                )
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
            self._received_fahrenheit_temperature = (
                restored.received_fahrenheit_temperature
            )
        if self._timer_deadline is not None:
            if self._timer_deadline <= dt_util.utcnow():
                self._expire_timer_power()
            else:
                self._schedule_timer_expiry()
        self._state.async_notify_switches()

    @property
    @override
    def extra_restore_state_data(self) -> _GreeAcExtraStoredData:
        """Return extra data to be restored alongside the entity's state."""
        return _GreeAcExtraStoredData(
            **super().extra_restore_state_data.as_dict(),
            last_active_hvac_mode=self._last_active_hvac_mode.value,
            turbo=self._state.turbo,
            light=self._state.light,
            health=self._state.health,
            xfan=self._state.xfan,
            sleep=self._state.sleep,
            ifeel=self._state.ifeel,
            swing_v=self._state.swing_v,
            swing_h=self._state.swing_h,
            swing_v_position=self._state.swing_v_position,
            fresh_air=self._state.fresh_air,
            timer_hours=self._state.timer_hours,
            timer_deadline=self._timer_deadline.isoformat()
            if self._timer_deadline
            else None,
            timer_expiry_power=self._timer_expiry_power,
            swing_h_position=self._state.swing_h_position,
            econo=self._state.econo,
            absence=self._state.absence,
            fahrenheit=self._state.fahrenheit,
            display_temp=self._state.display_temp,
            received_fahrenheit_temperature=self._received_fahrenheit_temperature,
        )

    def _remaining_timer_hours(self) -> float | None:
        """Return the active timer rounded to the protocol's half-hour step."""
        if self._timer_deadline is None:
            return self._state.timer_hours
        remaining = (self._timer_deadline - dt_util.utcnow()).total_seconds() / 3600
        if remaining <= 0:
            return None
        return max(0.5, int(remaining * 2 + 0.5) / 2)

    def _cancel_timer_expiry(self) -> None:
        """Cancel the scheduled timer expiry, if any."""
        if self._timer_expiry_unsub is not None:
            self._timer_expiry_unsub()
            self._timer_expiry_unsub = None

    def _schedule_timer_expiry(self) -> None:
        """Schedule state cleanup at the current timer deadline."""
        self._cancel_timer_expiry()
        if self._timer_deadline is not None:
            self._timer_expiry_unsub = async_track_point_in_utc_time(
                self.hass, self._handle_timer_expiry, self._timer_deadline
            )

    @callback
    def _handle_timer_expiry(self, now: datetime) -> None:
        """Queue timer cleanup behind any in-flight command."""
        self._timer_expiry_unsub = None
        config_entry = self.platform.config_entry
        assert config_entry is not None
        config_entry.async_create_background_task(
            self.hass, self._async_handle_timer_expiry(), "gree_infrared_timer_expiry"
        )

    def _expire_timer_power(self) -> None:
        """Clear an overdue timer and flip assumed HVAC power without transmitting.

        Explicit HVAC mode requests take precedence; unrelated staged settings do not
        mask timer expiry. A staged timer replacement retires only the old deadline.
        """
        self._cancel_timer_expiry()
        self._timer_deadline = None
        if not self._state.pending_timer_reset:
            self._state.timer_hours = None
        if self._state.pending_power_change or self._state.pending_timer_reset:
            return
        if self._timer_expiry_power is None:
            self._attr_hvac_mode = (
                self._last_active_hvac_mode
                if self._attr_hvac_mode is HVACMode.OFF
                else HVACMode.OFF
            )
        else:
            self._attr_hvac_mode = (
                self._last_active_hvac_mode
                if self._timer_expiry_power
                else HVACMode.OFF
            )

    def _reconcile_overdue_timer_locked(self) -> None:
        """Apply overdue timer power transition while holding the command lock.

        Setters that acquire the lock after the deadline but before the expiry
        background task must flip assumed HVAC power here; otherwise they still
        read the pre-expiry mode, transmit power=True, and clear the deadline so
        cleanup skips the transition.
        """
        if self._timer_deadline is None or dt_util.utcnow() < self._timer_deadline:
            return
        self._expire_timer_power()
        self.async_write_ha_state()
        self._state.async_notify_switches()

    async def _async_handle_timer_expiry(self) -> None:
        """Publish expiry only after pending state has committed or rolled back."""
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

    async def _async_flush_coalesced(self) -> None:
        """Send one frame with the final staged state after a quiet window."""
        state = self._state
        async with state.command_lock:
            self._reconcile_overdue_timer_locked()
            hvac_mode = self._attr_hvac_mode
            reset_timer = state.pending_timer_reset
            explicit_temp = state.pending_explicit_temp
            state.pending_timer_reset = False
            state.pending_explicit_temp = False
            state.coalesce_dirty = False
            if hvac_mode is None:
                return
            power = hvac_mode is not HVACMode.OFF
            active_hvac_mode = hvac_mode if power else self._last_active_hvac_mode
            command = self._build_command(
                active_hvac_mode,
                power,
                int(self._attr_native_target_temperature or MIN_TEMP),
                self._attr_fan_mode or FAN_AUTO,
                reset_timer=reset_timer,
                preserve_received_temperature=not explicit_temp,
            )
            try:
                await self._send_command(command)
            except HomeAssistantError as err:
                _LOGGER.warning(
                    "Coalesced Gree IR send failed; retaining staged settings: %s", err
                )
                # Failed timer replacement must not supersede the committed deadline.
                state.pending_timer_reset = False
                state.pending_power_change = False
                self._reconcile_overdue_timer_locked()
                if reset_timer:
                    state.timer_hours = (
                        self._remaining_timer_hours()
                        if self._timer_deadline is not None
                        else None
                    )
                    self.async_write_ha_state()
                    state.async_notify_switches()
                state.pending_explicit_temp = explicit_temp
                return
            state.timer_hours = command.timer_hours
            self._timer_deadline = (
                dt_util.utcnow() + timedelta(hours=command.timer_hours)
                if command.timer_hours is not None
                else None
            )
            self._timer_expiry_power = (
                not power if command.timer_hours is not None else None
            )
            self._schedule_timer_expiry()
            if explicit_temp:
                self._received_fahrenheit_temperature = None
            if power:
                self._last_active_hvac_mode = hvac_mode
            state.pending_power_change = False
            self.async_write_ha_state()
            state.async_notify_switches()

    def _options_for_mode(self, new_hvac_mode: HVACMode) -> dict[str, bool]:
        """Build option cancellations without publishing unconfirmed values."""
        options: dict[str, bool] = {}
        if (
            new_hvac_mode is HVACMode.OFF
            or new_hvac_mode != self._last_active_hvac_mode
        ) and self._state.sleep:
            options["sleep"] = False
        if new_hvac_mode is not HVACMode.COOL and self._state.econo:
            options["econo"] = False
        if new_hvac_mode is not HVACMode.HEAT and self._state.absence:
            options["absence"] = False
        return options

    def _stage_options_locked(self, options: dict[str, Any]) -> None:
        """Apply option flags and schedule one frame when the unit is active."""
        for key, value in options.items():
            setattr(self._state, key, value)
        hvac_mode = self._attr_hvac_mode
        if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
            if "timer_hours" in options:
                self._state.pending_timer_reset = True
            self._state.async_schedule_coalesced_flush(
                self.hass, self._async_flush_coalesced
            )

    async def async_set_option(self, option: str, value: bool) -> None:
        """Set an option flag and send the updated state when active."""
        if option in ("turbo", "light", "health", "xfan"):
            if not self._supports_options:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="unsupported_option"
                )
        elif option == "sleep":
            pass
        elif option in ("ifeel", "econo", "absence"):
            if not self._is_yap1f:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="unsupported_option"
                )
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unsupported_option"
            )
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            if (
                option == "sleep"
                and value
                and self._attr_hvac_mode
                in (
                    *SLEEP_BLOCKED_HVAC_MODES,
                    HVACMode.OFF,
                )
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="sleep_not_available"
                )
            if (
                option == "econo"
                and value
                and self._attr_hvac_mode is not HVACMode.COOL
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="econo_not_available"
                )
            if (
                option == "absence"
                and value
                and self._attr_hvac_mode is not HVACMode.HEAT
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="absence_not_available"
                )
            self._stage_options_locked({option: value})
            self._state.async_notify_switches()

    async def async_set_fresh_air(self, option: str) -> None:
        """Set the fresh-air intake level and send the updated state."""
        if option not in _HA_FRESH_AIR_TO_LIB:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unsupported_fresh_air"
            )
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            self._stage_options_locked({"fresh_air": int(_HA_FRESH_AIR_TO_LIB[option])})
            self._state.async_notify_switches()

    async def async_set_timer_hours(self, timer_hours: float | None) -> None:
        """Set the countdown timer (None = off) and send the updated state."""
        if timer_hours is not None and (
            not 0.5 <= timer_hours <= 24 or (timer_hours * 2) % 1
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unsupported_timer"
            )
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            self._state.timer_hours = timer_hours
            self._state.pending_timer_reset = True
            self._state.async_schedule_coalesced_flush(
                self.hass, self._async_flush_coalesced
            )
            self.async_write_ha_state()
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
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unsupported_vane_model"
            )
        if position is not None and position not in YAP1F_SWING_POSITIONS:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unsupported_vane_position"
            )
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            options: dict[str, Any] = {"swing_v_position": position}
            if position is not None:
                options["swing_v"] = False
            self._stage_options_locked(options)
            self._attr_swing_mode = SWING_ON if self._state.swing_v else SWING_OFF
            self.async_write_ha_state()
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
    async def async_turn_on(self) -> None:
        """Resume the last active mode instead of selecting a heating default."""
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()
            mode = self._attr_hvac_mode
            if mode is None or mode is HVACMode.OFF:
                mode = self._last_active_hvac_mode
            self._stage_hvac_mode_locked(mode)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            self._stage_hvac_mode_locked(hvac_mode)

    def _stage_hvac_mode_locked(self, hvac_mode: HVACMode) -> None:
        """Stage an HVAC mode change while holding the shared command lock."""
        for key, value in self._options_for_mode(hvac_mode).items():
            setattr(self._state, key, value)
        self._attr_hvac_mode = hvac_mode
        self._state.pending_power_change = True
        self.async_write_ha_state()
        self._state.async_notify_switches()
        self._state.async_schedule_coalesced_flush(
            self.hass, self._async_flush_coalesced
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, switching the HVAC mode when one is given."""
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            temp = round(kwargs[ATTR_TEMPERATURE])
            hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
            if hvac_mode is not None:
                self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)
                for key, value in self._options_for_mode(hvac_mode).items():
                    setattr(self._state, key, value)
            effective_mode = hvac_mode or self._attr_hvac_mode or HVACMode.OFF
            if hvac_mode is not None:
                self._attr_hvac_mode = hvac_mode
                self._state.pending_power_change = True
            self._attr_native_target_temperature = float(temp)
            if effective_mode is not HVACMode.OFF or hvac_mode is HVACMode.OFF:
                self._state.pending_explicit_temp = True
                self._state.async_schedule_coalesced_flush(
                    self.hass, self._async_flush_coalesced
                )
            else:
                self._received_fahrenheit_temperature = None
            self.async_write_ha_state()
            self._state.async_notify_switches()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            self._attr_fan_mode = fan_mode
            hvac_mode = self._attr_hvac_mode
            if hvac_mode is not None and hvac_mode is not HVACMode.OFF:
                self._state.async_schedule_coalesced_flush(
                    self.hass, self._async_flush_coalesced
                )
            self.async_write_ha_state()
            self._state.async_notify_switches()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set vertical sweep."""
        self._valid_mode_or_raise("swing", swing_mode, self.swing_modes)
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            self._stage_options_locked(
                {"swing_v": swing_mode == SWING_ON, "swing_v_position": None}
            )
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()
            self._state.async_notify_switches()

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set horizontal sweep."""
        self._valid_mode_or_raise(
            "horizontal_swing", swing_horizontal_mode, self.swing_horizontal_modes
        )
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            swing_h = swing_horizontal_mode == SWING_ON
            self._stage_options_locked(
                {"swing_h": swing_h, "swing_h_position": int(swing_h)}
            )
            self._attr_swing_horizontal_mode = swing_horizontal_mode
            self.async_write_ha_state()
            self._state.async_notify_switches()

    async def async_set_swing_h_position(self, position: int) -> None:
        """Set a fixed horizontal vane position, with zero following sweep."""
        if position not in range(7):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_horizontal_vane_position",
            )
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            self._stage_options_locked(
                {"swing_h_position": position, "swing_h": position != 0}
            )
            self._attr_swing_horizontal_mode = SWING_ON if position else SWING_OFF
            self.async_write_ha_state()
            self._state.async_notify_switches()

    async def async_set_display_temp(self, display_temp: int) -> None:
        """Select the temperature shown on the unit display."""
        if display_temp not in range(4):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_display_temperature",
            )
        await self._async_set_yap1f_field("display_temp", display_temp)

    async def async_set_fahrenheit(self, fahrenheit: bool) -> None:
        """Select the unit display scale independent of HA's climate unit."""
        await self._async_set_yap1f_field("fahrenheit", fahrenheit)

    async def _async_set_yap1f_field(self, key: str, value: Any) -> None:
        """Stage one YAP1F command field for the next coalesced frame."""
        if not self._is_yap1f:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unsupported_yap1f_field"
            )
        async with self._state.command_lock:
            self._reconcile_overdue_timer_locked()

            previous = getattr(self._state, key)
            self._stage_options_locked({key: value})
            if key == "fahrenheit" and value != previous:
                self._state.pending_explicit_temp = True
            self.async_write_ha_state()
            self._state.async_notify_switches()

    def _build_command(
        self,
        hvac_mode: HVACMode,
        power: bool,
        temp: int,
        fan_mode: str,
        *,
        state: GreeAcState | None = None,
        reset_timer: bool = False,
        preserve_received_temperature: bool = True,
    ) -> GreeAcCommand:
        """Build a command from a mode, power state, a temperature and a fan mode."""
        state = state or self._state
        if self._is_yap1f and state.fahrenheit:
            if (
                preserve_received_temperature
                and state.fahrenheit == self._state.fahrenheit
                and self._received_fahrenheit_temperature is not None
            ):
                temp = self._received_fahrenheit_temperature
            else:
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
            swing_v=state.swing_v,
            swing_h=state.swing_h,
            turbo=state.turbo,
            display=state.light,
            anion=state.health,
            blow=state.xfan,
            sleep=state.sleep,
            timer_hours=state.timer_hours
            if reset_timer
            else self._remaining_timer_hours(),
            fresh_air=GreeAcFreshAir(state.fresh_air),
            ifeel=state.ifeel if self._is_yap1f else False,
            swing_v_position=state.swing_v_position if self._is_yap1f else None,
            swing_h_position=(
                state.swing_h_position if self._is_yap1f else int(state.swing_h)
            ),
            fahrenheit=state.fahrenheit if self._is_yap1f else False,
            econo=state.econo if self._is_yap1f else False,
            absence=state.absence if self._is_yap1f else False,
            display_temp=state.display_temp if self._is_yap1f else None,
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
        config_entry = self.platform.config_entry
        assert config_entry is not None
        config_entry.async_create_background_task(
            self.hass,
            self._async_handle_signal(signal),
            "gree_infrared_received_signal",
        )

    async def _async_handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal under the command lock."""
        async with self._state.command_lock:
            if self._state.climate is not self:
                return
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
        # The received frame supersedes anything staged but unsent.
        self._state.clear_coalesced()
        self._received_fahrenheit_temperature = (
            command.temperature if command.fahrenheit else None
        )
        temperature = command.temperature
        if command.fahrenheit:
            # HA shows a Celsius target; the exact wire °F is retained separately
            # so later commands cannot drift through a lossy F→C→F round trip.
            temperature = round(
                TemperatureConverter.convert(
                    temperature,
                    UnitOfTemperature.FAHRENHEIT,
                    UnitOfTemperature.CELSIUS,
                )
            )
        self._attr_native_target_temperature = float(temperature)
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
        self._timer_expiry_power = (
            not command.power if command.timer_hours is not None else None
        )
        self._schedule_timer_expiry()
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
