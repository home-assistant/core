"""Class to hold all heater cooler accessories."""

import logging
from typing import Any

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
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

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

HC_HASS_TO_HOMEKIT_TARGET = {
    HVACMode.OFF: HC_TARGET_AUTO,  # Default to Auto when off
    HVACMode.HEAT: HC_TARGET_HEAT,
    HVACMode.COOL: HC_TARGET_COOL,
    HVACMode.HEAT_COOL: HC_TARGET_AUTO,
    HVACMode.AUTO: HC_TARGET_AUTO,
}

# Base reverse mapping (will be dynamically adjusted per entity)
HC_HOMEKIT_TO_HASS_TARGET_BASE = {
    HC_TARGET_HEAT: HVACMode.HEAT,
    HC_TARGET_COOL: HVACMode.COOL,
}

HC_HASS_TO_HOMEKIT_ACTION = {
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


def _get_current_temperature(state: State, unit: str) -> float | None:
    """Return current temperature converted to HomeKit unit."""
    current_temp = state.attributes.get(ATTR_CURRENT_TEMPERATURE)
    if current_temp is None:
        return None
    return temperature_to_homekit(current_temp, unit)


def _temp(state: State, key: str, unit: str) -> float | None:
    """Return a temperature attribute converted to HomeKit unit."""
    if (val := state.attributes.get(key)) is None:
        return None
    return temperature_to_homekit(val, unit)


@TYPES.register("HeaterCooler")
class HeaterCooler(HomeAccessory):
    """Generate a HeaterCooler accessory for a climate entity."""

    def __init__(self, *args: Any) -> None:
        """Initialize a HeaterCooler accessory object."""
        super().__init__(*args, category=CATEGORY_THERMOSTAT)
        self._unit = self.hass.config.units.temperature_unit

        state = self.hass.states.get(self.entity_id)
        assert state
        attributes = state.attributes
        features = attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # Determine what modes this entity supports
        hvac_modes = attributes.get(ATTR_HVAC_MODES, [])
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

        raw_step = attributes.get("temperature_step", 1)
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
        if features & ClimateEntityFeature.FAN_MODE:
            chars.append(CHAR_ROTATION_SPEED)
        if features & ClimateEntityFeature.SWING_MODE:
            chars.append(CHAR_SWING_MODE)

        serv = self.add_preload_service(SERV_HEATER_COOLER, chars)
        self.set_primary_service(serv)

        # basic chars
        self.char_active = serv.configure_char(CHAR_ACTIVE, value=0)
        self.char_current_state = serv.configure_char(
            CHAR_CURRENT_HEATER_COOLER_STATE, value=HC_INACTIVE
        )
        self.char_target_state = serv.configure_char(
            CHAR_TARGET_HEATER_COOLER_STATE, value=HC_TARGET_AUTO
        )
        self.char_current_temp = serv.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=21.0
        )

        # set-point chars
        min_temp_c = attributes.get(ATTR_MIN_TEMP, 7.0)
        max_temp_c = attributes.get(ATTR_MAX_TEMP, 35.0)
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
            properties=temp_properties,
        )
        self.char_heat = serv.configure_char(
            CHAR_HEATING_THRESHOLD_TEMPERATURE,
            value=24.0,
            properties=temp_properties,
        )

        # fan / swing
        self.ordered_fan_speeds: list[str] = []
        if features & ClimateEntityFeature.FAN_MODE and (
            modes := attributes.get(ATTR_FAN_MODES)
        ):
            fm = {m.lower(): m for m in modes}
            self.ordered_fan_speeds = [s for s in ORDERED_FAN_SPEEDS if s in fm]
            self.char_speed = serv.configure_char(
                CHAR_ROTATION_SPEED,
                value=100,
                properties={PROP_MIN_STEP: 100 / len(self.ordered_fan_speeds)},
            )
            self.fan_modes = fm

        if features & ClimateEntityFeature.SWING_MODE and (
            sw := attributes.get(ATTR_SWING_MODES)
        ):
            self.swing_on_mode = next(
                (m for m in sw if m.lower() in SWING_ON_SET), sw[0]
            )
            self.char_swing = serv.configure_char(CHAR_SWING_MODE, value=0)

        # Smart mode change tracking
        self._last_known_mode: HVACMode = current_mode or HVACMode.COOL

        # initialise
        self.async_update_state(state)

        # Set service-level setter callback to handle all characteristic changes at once
        serv.setter_callback = self._set_chars

    def get_temperature_range(self, state: State) -> tuple[float, float]:
        """Return min and max temperature range."""
        min_temp_c = state.attributes.get(ATTR_MIN_TEMP, 7.0)
        max_temp_c = state.attributes.get(ATTR_MAX_TEMP, 35.0)
        min_temp_hk = temperature_to_homekit(min_temp_c, self._unit)
        max_temp_hk = temperature_to_homekit(max_temp_c, self._unit)

        # Handle reversed temperature range and apply HomeKit constraints
        min_temp_hk = max(min_temp_hk, 0)
        max_temp_hk = max(max_temp_hk, min_temp_hk)

        return min_temp_hk, max_temp_hk

    def _temperature_to_homekit(self, temp: float) -> float:
        """Convert temperature to HomeKit units."""
        return temperature_to_homekit(temp, self._unit)

    def _temperature_to_states(self, temp: float) -> float:
        """Convert temperature to Home Assistant units."""
        return temperature_to_states(temp, self._unit)

    def _set_fan_speed(self, speed: int) -> None:
        """Set the fan speed."""
        if not self.ordered_fan_speeds:
            return

        if 0 < speed <= 100:
            # Convert percentage to fan mode
            fan_mode = percentage_to_ordered_list_item(self.ordered_fan_speeds, speed)
            fan_mode = self.fan_modes.get(fan_mode, fan_mode)

            try:
                self.async_call_service(
                    "climate",
                    "set_fan_mode",
                    {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: fan_mode},
                )
            except (ServiceNotFound, ServiceValidationError) as e:
                _LOGGER.error("Failed to set fan mode: %s", e)

    def _set_swing_mode(self, swing_on: int) -> None:
        """Set the swing mode."""
        if not hasattr(self, "swing_on_mode"):
            return

        state = self.hass.states.get(self.entity_id)
        if not state:
            return

        swing_modes = state.attributes.get(ATTR_SWING_MODES, [])
        current_swing = state.attributes.get(ATTR_SWING_MODE)

        if swing_on:
            # Turn swing on - use the detected swing-on mode
            target_mode = self.swing_on_mode
        else:
            # Turn swing off - find an "off" mode
            off_modes = {"off", "false", "0"}
            target_mode = next(
                (m for m in swing_modes if m.lower() in off_modes),
                swing_modes[0] if swing_modes else "off",
            )

        if target_mode != current_swing:
            try:
                self.async_call_service(
                    "climate",
                    "set_swing_mode",
                    {ATTR_ENTITY_ID: self.entity_id, ATTR_SWING_MODE: target_mode},
                )
            except (ServiceNotFound, ServiceValidationError) as e:
                _LOGGER.error("Failed to set swing mode: %s", e)

    def _set_chars(self, char_values: dict[str, Any]) -> None:
        """Handle writes to multiple HeaterCooler characteristics at once."""
        _LOGGER.debug("HeaterCooler _set_chars: %s", char_values)
        # Collect all the service calls we need to make
        service_calls: list[tuple[str, dict[str, Any]]] = []

        # Handle active/mode changes first (they might affect temperature handling)
        self._handle_active_mode_changes(char_values, service_calls)

        # Handle temperature changes
        self._handle_temperature_changes(char_values, service_calls)

        # Handle fan speed and swing mode changes
        self._handle_fan_swing_changes(char_values, service_calls)

        # Execute all service calls
        for service_name, service_data in service_calls:
            try:
                self.async_call_service(
                    "climate",
                    service_name,
                    {ATTR_ENTITY_ID: self.entity_id, **service_data},
                )
            except (ServiceNotFound, ServiceValidationError) as e:
                _LOGGER.error("Failed to execute %s: %s", service_name, e)

    def _handle_active_mode_changes(
        self,
        char_values: dict[str, Any],
        service_calls: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Handle active and mode changes."""
        active = char_values.get(CHAR_ACTIVE)
        target_mode = char_values.get(CHAR_TARGET_HEATER_COOLER_STATE)

        # Check if we're already active to avoid redundant commands
        current_state = self.hass.states.get(self.entity_id)
        currently_active = current_state and current_state.state not in (
            HVACMode.OFF,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        )

        if active is not None or target_mode is not None:
            # Smart mode/active handling
            if active == 0:
                # Always turn off when explicitly requested
                service_calls.append(("turn_off", {}))
            elif target_mode is not None:
                # Mode change requested
                hass_mode = self._hk_to_ha_target.get(target_mode)
                if hass_mode:
                    service_calls.append(("set_hvac_mode", {ATTR_HVAC_MODE: hass_mode}))
                    if isinstance(hass_mode, HVACMode):
                        self._last_known_mode = hass_mode
            elif active == 1 and not currently_active:
                # Only turn on if not already active
                service_calls.append(
                    ("set_hvac_mode", {ATTR_HVAC_MODE: self._last_known_mode})
                )

    def _handle_temperature_changes(
        self,
        char_values: dict[str, Any],
        service_calls: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Handle temperature changes."""
        cooling_temp = char_values.get(CHAR_COOLING_THRESHOLD_TEMPERATURE)
        heating_temp = char_values.get(CHAR_HEATING_THRESHOLD_TEMPERATURE)

        if cooling_temp is not None or heating_temp is not None:
            current_state = self.hass.states.get(self.entity_id)
            supports_dual_temp = current_state and (
                ATTR_TARGET_TEMP_HIGH in current_state.attributes
                or ATTR_TARGET_TEMP_LOW in current_state.attributes
            )

            if supports_dual_temp:
                self._handle_dual_temp_changes(
                    service_calls, cooling_temp, heating_temp
                )
            else:
                self._handle_single_temp_changes(
                    service_calls, cooling_temp, heating_temp
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
        self,
        char_values: dict[str, Any],
        service_calls: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Handle fan speed and swing mode changes."""
        # Handle fan speed
        if CHAR_ROTATION_SPEED in char_values:
            self._set_fan_speed(char_values[CHAR_ROTATION_SPEED])

        # Handle swing mode
        if CHAR_SWING_MODE in char_values:
            self._set_swing_mode(char_values[CHAR_SWING_MODE])

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
        """Update state without rechecking the device features."""
        attributes = new_state.attributes
        features = attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        current_mode = try_parse_enum(HVACMode, new_state.state)
        if current_mode and current_mode != HVACMode.OFF:
            self._last_known_mode = current_mode

        if (tgt := self._hk_target_mode(new_state)) is not None:
            self.char_target_state.set_value(tgt)

        action = attributes.get(ATTR_HVAC_ACTION) or self._derive_action(new_state)
        hk_current_state = HC_HASS_TO_HOMEKIT_ACTION.get(action, HC_INACTIVE)
        self.char_current_state.set_value(hk_current_state)

        active_value = int(
            new_state.state not in (HVACMode.OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)
        )
        self.char_active.set_value(active_value)

        if (cur := _get_current_temperature(new_state, self._unit)) is not None:
            self.char_current_temp.set_value(cur)

        self._update_temperature_thresholds(new_state)

        # Update fan and swing state if supported
        if features & (ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.SWING_MODE):
            self._async_update_fan_state(new_state)

    def _update_temperature_thresholds(self, state: State) -> None:
        """Update HomeKit temperature thresholds based on HA state."""
        attributes = state.attributes

        supports_dual_temp = (
            ATTR_TARGET_TEMP_HIGH in attributes or ATTR_TARGET_TEMP_LOW in attributes
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

    def _async_update_fan_state(self, new_state: State) -> None:
        """Update the fan speed characteristic from state."""
        attributes = new_state.attributes

        # Update fan speed
        if self.ordered_fan_speeds and hasattr(self, "char_speed"):
            current_fan_mode = attributes.get(ATTR_FAN_MODE)
            if current_fan_mode and current_fan_mode in self.fan_modes.values():
                # Find the key that maps to this fan mode
                for ordered_mode in self.ordered_fan_speeds:
                    if self.fan_modes.get(ordered_mode) == current_fan_mode:
                        percentage = ordered_list_item_to_percentage(
                            self.ordered_fan_speeds, ordered_mode
                        )
                        self.char_speed.set_value(percentage)
                        break

        # Update swing mode
        if hasattr(self, "char_swing"):
            current_swing = attributes.get(ATTR_SWING_MODE, "").lower()
            swing_on = current_swing in SWING_ON_SET
            self.char_swing.set_value(1 if swing_on else 0)

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
