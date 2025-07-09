"""HomeKit Heater-Cooler accessory (single tile: temp / speed / swing)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Final

from pyhap.const import CATEGORY_THERMOSTAT

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State, callback
from homeassistant.exceptions import ServiceNotFound, ServiceValidationError
from homeassistant.util.enum import try_parse_enum
from homeassistant.util.percentage import ordered_list_item_to_percentage

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_COOLING_THRESHOLD_TEMPERATURE,
    CHAR_CURRENT_HEATER_COOLER_STATE,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_HEATING_THRESHOLD_TEMPERATURE,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_HEATER_COOLER_STATE,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
    SERV_HEATER_COOLER,
)
from .util import temperature_to_homekit, temperature_to_states

_LOGGER = logging.getLogger(__name__)

# HomeKit CurrentHeaterCoolerState values (per HomeKit spec)
HC_INACTIVE, HC_IDLE, HC_HEATING, HC_COOLING = range(4)

# HomeKit TargetHeaterCoolerState valid values: Auto=0, Heat=1, Cool=2
HC_TARGET_AUTO, HC_TARGET_HEAT, HC_TARGET_COOL = range(3)

HC_HASS_TO_HOMEKIT_TARGET: Final = {
    HVACMode.OFF: HC_TARGET_AUTO,  # Default to Auto when off
    HVACMode.HEAT: HC_TARGET_HEAT,
    HVACMode.COOL: HC_TARGET_COOL,
    HVACMode.HEAT_COOL: HC_TARGET_AUTO,
    HVACMode.AUTO: HC_TARGET_AUTO,
}

# Base reverse mapping (will be dynamically adjusted per entity)
HC_HOMEKIT_TO_HASS_TARGET_BASE: Final = {
    HC_TARGET_HEAT: HVACMode.HEAT,
    HC_TARGET_COOL: HVACMode.COOL,
}

HC_HASS_TO_HOMEKIT_ACTION: Final = {
    HVACAction.OFF: HC_INACTIVE,
    HVACAction.IDLE: HC_IDLE,
    HVACAction.HEATING: HC_HEATING,
    HVACAction.PREHEATING: HC_HEATING,
    HVACAction.COOLING: HC_COOLING,
    HVACAction.DRYING: HC_COOLING,
    HVACAction.FAN: HC_COOLING,
    HVACAction.DEFROSTING: HC_HEATING,
}

ORDERED_FAN_SPEEDS = ["auto", FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH]
SWING_ON_SET = {"on", "both", "horizontal", "vertical"}


def _temp(state: State, key: str, unit: str) -> float | None:
    """Return a temperature attribute converted to HomeKit unit."""
    if (val := state.attributes.get(key)) is None:
        return None
    return temperature_to_homekit(val, unit)


@TYPES.register("HeaterCooler")
class HeaterCooler(HomeAccessory):
    """Expose a HA climate entity as a native HeaterCooler service."""

    def __init__(self, *args: Any) -> None:
        """Build the Heater-Cooler accessory and register HomeKit callbacks."""
        super().__init__(*args, category=CATEGORY_THERMOSTAT)
        self._unit = self.hass.config.units.temperature_unit

        state = self.hass.states.get(self.entity_id)
        assert state
        attrs = state.attributes
        feats = attrs.get(ATTR_SUPPORTED_FEATURES, 0)

        # Determine what modes this entity supports
        hvac_modes = attrs.get(ATTR_HVAC_MODES, [])
        current_mode = try_parse_enum(HVACMode, state.state)

        # Check if entity supports auto or heat_cool modes
        self._supports_auto = HVACMode.AUTO in hvac_modes
        self._supports_heat_cool = HVACMode.HEAT_COOL in hvac_modes

        if current_mode == HVACMode.AUTO:
            self._supports_auto = True
        elif current_mode == HVACMode.HEAT_COOL:
            self._supports_heat_cool = True

        # Build dynamic mapping from HomeKit to HA modes
        self._hk_to_ha_target = HC_HOMEKIT_TO_HASS_TARGET_BASE.copy()

        if self._supports_auto:
            self._hk_to_ha_target[HC_TARGET_AUTO] = HVACMode.AUTO
        elif self._supports_heat_cool:
            self._hk_to_ha_target[HC_TARGET_AUTO] = HVACMode.HEAT_COOL
        else:
            self._hk_to_ha_target[HC_TARGET_AUTO] = HVACMode.HEAT_COOL

        raw_step = attrs.get("temperature_step", 1)
        try:
            self._step: float = float(raw_step)
        except (TypeError, ValueError):
            self._step = 1.0

        # build characteristic list
        chars: list[str] = [
            CHAR_ACTIVE,
            CHAR_CURRENT_HEATER_COOLER_STATE,
            CHAR_TARGET_HEATER_COOLER_STATE,
            CHAR_CURRENT_TEMPERATURE,
            CHAR_COOLING_THRESHOLD_TEMPERATURE,
            CHAR_HEATING_THRESHOLD_TEMPERATURE,
        ]
        if feats & ClimateEntityFeature.FAN_MODE:
            chars.append(CHAR_ROTATION_SPEED)
        if feats & ClimateEntityFeature.SWING_MODE:
            chars.append(CHAR_SWING_MODE)

        serv = self.add_preload_service(SERV_HEATER_COOLER, chars)
        self.set_primary_service(serv)

        # basic chars
        self.char_active = serv.configure_char(
            CHAR_ACTIVE, value=0, setter_callback=self._set_active
        )
        self.char_current_state = serv.configure_char(
            CHAR_CURRENT_HEATER_COOLER_STATE, value=HC_INACTIVE
        )
        self.char_target_state = serv.configure_char(
            CHAR_TARGET_HEATER_COOLER_STATE,
            value=HC_TARGET_AUTO,
            setter_callback=self._set_target_state,
        )
        self.char_current_temp = serv.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=21.0
        )

        # set-point chars
        min_temp_c = attrs.get(ATTR_MIN_TEMP, 7.0)
        max_temp_c = attrs.get(ATTR_MAX_TEMP, 35.0)
        min_temp_hk = temperature_to_homekit(min_temp_c, self._unit)
        max_temp_hk = temperature_to_homekit(max_temp_c, self._unit)

        step_hk = self._step
        if self._unit != "°C":
            step_hk = self._step * 5.0 / 9.0

        temp_properties = {
            PROP_MIN_VALUE: min_temp_hk,
            PROP_MAX_VALUE: max_temp_hk,
            PROP_MIN_STEP: step_hk,
        }

        self.char_cool = serv.configure_char(
            CHAR_COOLING_THRESHOLD_TEMPERATURE,
            value=24.0,
            setter_callback=self._set_cooling_threshold,
            properties=temp_properties,
        )
        self.char_heat = serv.configure_char(
            CHAR_HEATING_THRESHOLD_TEMPERATURE,
            value=24.0,
            setter_callback=self._set_heating_threshold,
            properties=temp_properties,
        )

        # fan / swing
        self.ordered_fan_speeds: list[str] = []
        if feats & ClimateEntityFeature.FAN_MODE and (
            modes := attrs.get(ATTR_FAN_MODES)
        ):
            fm = {m.lower(): m for m in modes}
            self.ordered_fan_speeds = [s for s in ORDERED_FAN_SPEEDS if s in fm]
            self.char_speed = serv.configure_char(
                CHAR_ROTATION_SPEED,
                value=100,
                properties={PROP_MIN_STEP: 100 / len(self.ordered_fan_speeds)},
                setter_callback=self._set_fan_speed,
            )
            self.fan_modes = fm

        if feats & ClimateEntityFeature.SWING_MODE and (
            sw := attrs.get(ATTR_SWING_MODES)
        ):
            self.swing_on_mode = next(
                (m for m in sw if m.lower() in SWING_ON_SET), sw[0]
            )
            self.char_swing = serv.configure_char(
                CHAR_SWING_MODE, value=0, setter_callback=self._set_swing_mode
            )

        # Single debouncing mechanism
        self._pending_state: dict[str, Any] = {
            "active": None,
            "target_mode": None,
            "cooling_temp": None,
            "heating_temp": None,
            "rotation_speed": None,
            "swing_mode": None,
        }
        self._debounce_timer: asyncio.Task | None = None
        self._debounce_delay = 0.6

        # Smart mode change tracking
        self._last_known_mode: HVACMode = current_mode or HVACMode.COOL

        # initialise
        self.async_update_state(state)

    def _schedule_debounced_execution(self) -> None:
        """Schedule execution of all pending state changes after debounce delay."""
        # Cancel any existing timer
        if self._debounce_timer and not self._debounce_timer.done():
            self._debounce_timer.cancel()

        async def execute_pending_state() -> None:
            """Execute all pending state changes after debounce delay."""
            try:
                await asyncio.sleep(self._debounce_delay)

                # Collect all the service calls we need to make
                service_calls: list[
                    tuple[str, dict[str, Any]]
                ] = []  # Handle active/mode changes first (they might affect temperature handling)
                self._handle_active_mode_changes(service_calls)

                # Handle temperature changes
                self._handle_temperature_changes(service_calls)

                # Handle fan speed and swing mode changes
                self._handle_fan_swing_changes(service_calls)

                # Execute all service calls
                for service_name, service_data in service_calls:
                    try:
                        await self.hass.services.async_call(
                            "climate",
                            service_name,
                            {ATTR_ENTITY_ID: self.entity_id, **service_data},
                        )
                    except (ServiceNotFound, ServiceValidationError) as e:
                        _LOGGER.error("Failed to execute %s: %s", service_name, e)

                # Clear pending state
                self._pending_state = {
                    "active": None,
                    "target_mode": None,
                    "cooling_temp": None,
                    "heating_temp": None,
                    "rotation_speed": None,
                    "swing_mode": None,
                }
            except asyncio.CancelledError:
                # Task was cancelled, ignore
                pass
            except Exception:
                _LOGGER.exception("Error in debounced execution")

        # Schedule the execution
        self._debounce_timer = asyncio.create_task(execute_pending_state())

    def _handle_active_mode_changes(
        self, service_calls: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Handle active and mode changes."""
        active = self._pending_state["active"]
        target_mode = self._pending_state["target_mode"]

        if active is not None or target_mode is not None:
            # Smart mode/active handling
            if active == 0:
                service_calls.append(("turn_off", {}))
            elif target_mode is not None:
                service_calls.append(("set_hvac_mode", {ATTR_HVAC_MODE: target_mode}))
                if isinstance(target_mode, HVACMode):
                    self._last_known_mode = target_mode
            elif active == 1:
                service_calls.append(
                    ("set_hvac_mode", {ATTR_HVAC_MODE: self._last_known_mode})
                )

    def _handle_temperature_changes(
        self, service_calls: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Handle temperature changes."""
        cooling_temp = self._pending_state["cooling_temp"]
        heating_temp = self._pending_state["heating_temp"]

        if cooling_temp is not None or heating_temp is not None:
            # Ensure types are correct
            cooling_temp_val = (
                cooling_temp if isinstance(cooling_temp, (int, float)) else None
            )
            heating_temp_val = (
                heating_temp if isinstance(heating_temp, (int, float)) else None
            )

            current_state = self.hass.states.get(self.entity_id)
            supports_dual_temp = current_state and (
                ATTR_TARGET_TEMP_HIGH in current_state.attributes
                or ATTR_TARGET_TEMP_LOW in current_state.attributes
            )

            if supports_dual_temp:
                self._handle_dual_temp_changes(
                    service_calls, cooling_temp_val, heating_temp_val
                )
            else:
                self._handle_single_temp_changes(
                    service_calls, cooling_temp_val, heating_temp_val
                )

    def _handle_dual_temp_changes(
        self,
        service_calls: list[tuple[str, dict[str, Any]]],
        cooling_temp: float | None,
        heating_temp: float | None,
    ) -> None:
        """Handle temperature changes for dual-temperature entities."""
        temp_data = {}

        if cooling_temp is not None:
            ha_temp = temperature_to_states(cooling_temp, self._unit)
            temp_data[ATTR_TARGET_TEMP_HIGH] = ha_temp
        if heating_temp is not None:
            ha_temp = temperature_to_states(heating_temp, self._unit)
            temp_data[ATTR_TARGET_TEMP_LOW] = ha_temp

        if temp_data:
            service_calls.append(("set_temperature", temp_data))

    def _handle_single_temp_changes(
        self,
        service_calls: list[tuple[str, dict[str, Any]]],
        cooling_temp: float | None,
        heating_temp: float | None,
    ) -> None:
        """Handle temperature changes for single-temperature entities."""
        current_state = self.hass.states.get(self.entity_id)
        if not current_state:
            return

        current_mode = current_state.state

        # Determine which temperature to use
        selected_temp = None
        if current_mode == HVACMode.COOL and cooling_temp is not None:
            selected_temp = cooling_temp
        elif current_mode == HVACMode.HEAT and heating_temp is not None:
            selected_temp = heating_temp
        elif current_mode == HVACMode.HEAT_COOL:
            # For heat_cool mode, prefer the temperature that was set
            if cooling_temp is not None and heating_temp is not None:
                # If both are set, use the one that's different from current
                current_temp = current_state.attributes.get(ATTR_TEMPERATURE)
                if current_temp and abs(cooling_temp - current_temp) > abs(
                    heating_temp - current_temp
                ):
                    selected_temp = cooling_temp
                else:
                    selected_temp = heating_temp
            elif cooling_temp is not None:
                selected_temp = cooling_temp
            elif heating_temp is not None:
                selected_temp = heating_temp
        # For other modes or when no mode-specific logic applies,
        # accept any temperature that was set (HomeKit behavior)
        elif cooling_temp is not None:
            selected_temp = cooling_temp
        elif heating_temp is not None:
            selected_temp = heating_temp

        if selected_temp is not None:
            ha_temp = temperature_to_states(selected_temp, self._unit)
            service_calls.append(("set_temperature", {ATTR_TEMPERATURE: ha_temp}))

    def _handle_fan_swing_changes(
        self, service_calls: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Handle fan speed and swing mode changes."""
        # Handle fan speed changes
        fan_speed = self._pending_state["rotation_speed"]
        if (
            fan_speed is not None
            and self.ordered_fan_speeds
            and isinstance(fan_speed, (int, float))
        ):
            fan_index = min(
                len(self.ordered_fan_speeds) - 1,
                int(fan_speed * len(self.ordered_fan_speeds) / 100),
            )
            fan_mode = self.ordered_fan_speeds[fan_index]
            ha_fan_mode = self.fan_modes.get(fan_mode, fan_mode)
            service_calls.append(("set_fan_mode", {ATTR_FAN_MODE: ha_fan_mode}))

        # Handle swing mode changes
        swing_mode = self._pending_state["swing_mode"]
        if swing_mode is not None and hasattr(self, "swing_on_mode"):
            swing_value = self.swing_on_mode if swing_mode else "off"
            service_calls.append(("set_swing_mode", {ATTR_SWING_MODE: swing_value}))

    def _set_target_state(self, value: int) -> None:
        """Handle writes to TargetHeaterCoolerState from HomeKit."""
        _LOGGER.debug("%s: Set target state to %d", self.entity_id, value)
        if value not in self._hk_to_ha_target:
            return

        target_mode = self._hk_to_ha_target[value]
        self._pending_state["target_mode"] = target_mode
        self._schedule_debounced_execution()

    def _set_active(self, value: int) -> None:
        """Handle writes to Active from HomeKit."""
        _LOGGER.debug("%s: Set active to %d", self.entity_id, value)
        self._pending_state["active"] = value
        self._schedule_debounced_execution()

    def _set_cooling_threshold(self, value: float) -> None:
        """Handle writes to CoolingThresholdTemperature from HomeKit."""
        _LOGGER.debug("%s: Set cooling threshold to %.1f°C", self.entity_id, value)
        self._pending_state["cooling_temp"] = value
        self._schedule_debounced_execution()

    def _set_heating_threshold(self, value: float) -> None:
        """Handle writes to HeatingThresholdTemperature from HomeKit."""
        _LOGGER.debug("%s: Set heating threshold to %.1f°C", self.entity_id, value)
        self._pending_state["heating_temp"] = value
        self._schedule_debounced_execution()

    def _set_fan_speed(self, value: int) -> None:
        """Handle writes to RotationSpeed from HomeKit."""
        _LOGGER.debug("%s: Set fan speed to %d", self.entity_id, value)
        self._pending_state["rotation_speed"] = value
        self._schedule_debounced_execution()

    def _set_swing_mode(self, value: int) -> None:
        """Handle writes to SwingMode from HomeKit."""
        _LOGGER.debug("%s: Set swing mode to %d", self.entity_id, value)
        self._pending_state["swing_mode"] = value
        self._schedule_debounced_execution()

    def _hk_target_mode(self, state: State) -> int | None:
        """Map HA hvac_mode → HomeKit target heater-cooler state."""
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        if not (mode := try_parse_enum(HVACMode, state.state)):
            return None

        # Use dynamic mapping - only return values that are valid for this entity
        hk_value = HC_HASS_TO_HOMEKIT_TARGET.get(mode)
        if hk_value is not None and hk_value in self._hk_to_ha_target:
            return hk_value
        return None

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Mirror each Home Assistant state update to HomeKit."""
        attrs = new_state.attributes
        feats = attrs.get(ATTR_SUPPORTED_FEATURES, 0)

        current_mode = try_parse_enum(HVACMode, new_state.state)
        if current_mode and current_mode != HVACMode.OFF:
            self._last_known_mode = current_mode

        if (tgt := self._hk_target_mode(new_state)) is not None:
            self.char_target_state.set_value(tgt)

        action = attrs.get(ATTR_HVAC_ACTION) or self._derive_action(new_state)
        hk_current_state = HC_HASS_TO_HOMEKIT_ACTION.get(action, HC_INACTIVE)
        self.char_current_state.set_value(hk_current_state)

        active_value = int(
            new_state.state not in (HVACMode.OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)
        )
        self.char_active.set_value(active_value)

        if (cur := _temp(new_state, ATTR_CURRENT_TEMPERATURE, self._unit)) is not None:
            self.char_current_temp.set_value(cur)

        self._update_temperature_thresholds(new_state)

        if feats & ClimateEntityFeature.FAN_MODE and self.ordered_fan_speeds:
            fm = attrs.get(ATTR_FAN_MODE)
            if fm and (fm_l := fm.lower()) in self.ordered_fan_speeds:
                self.char_speed.set_value(
                    ordered_list_item_to_percentage(self.ordered_fan_speeds, fm_l)
                )

        if feats & ClimateEntityFeature.SWING_MODE and hasattr(self, "char_swing"):
            sw = attrs.get(ATTR_SWING_MODE)
            self.char_swing.set_value(1 if sw and sw.lower() in SWING_ON_SET else 0)

    def _update_temperature_thresholds(self, state: State) -> None:
        """Update HomeKit temperature thresholds based on HA state."""
        attrs = state.attributes

        supports_dual_temp = (
            ATTR_TARGET_TEMP_HIGH in attrs or ATTR_TARGET_TEMP_LOW in attrs
        )

        if supports_dual_temp:
            if (
                high_temp := _temp(state, ATTR_TARGET_TEMP_HIGH, self._unit)
            ) is not None:
                self.char_cool.set_value(high_temp)

            if (low_temp := _temp(state, ATTR_TARGET_TEMP_LOW, self._unit)) is not None:
                self.char_heat.set_value(low_temp)
        elif (target_temp := _temp(state, ATTR_TEMPERATURE, self._unit)) is not None:
            self.char_cool.set_value(target_temp)
            self.char_heat.set_value(target_temp)

    def _derive_action(self, state: State) -> HVACAction:
        """Infer heating / cooling when integration omits hvac_action."""
        mode = try_parse_enum(HVACMode, state.state)
        tgt = (
            state.attributes.get(ATTR_TEMPERATURE)
            or state.attributes.get(ATTR_TARGET_TEMP_HIGH)
            or state.attributes.get(ATTR_TARGET_TEMP_LOW)
        )
        cur = state.attributes.get(ATTR_CURRENT_TEMPERATURE)
        if cur is None or tgt is None or mode is None:
            return HVACAction.IDLE

        delta = 0.25  # °C hysteresis

        if mode == HVACMode.COOL:
            return HVACAction.COOLING if cur > tgt + delta else HVACAction.IDLE
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING if cur < tgt - delta else HVACAction.IDLE
        if mode in (HVACMode.HEAT_COOL, HVACMode.AUTO):
            if cur > tgt + delta:
                return HVACAction.COOLING
            if cur < tgt - delta:
                return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_wait_for_debounced_execution(self) -> None:
        """Wait for any pending debounced execution to complete. Used for testing."""
        if self._debounce_timer and not self._debounce_timer.done():
            with contextlib.suppress(asyncio.CancelledError):
                await self._debounce_timer
