"""Class to hold all heater cooler accessories."""

import logging
from typing import Any, override

from pyhap.characteristic import Characteristic

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
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
from homeassistant.util.enum import try_parse_enum

from .accessories import TYPES
from .climate_base import HomeKitClimateAccessory
from .climate_util import temperature_attribute_to_homekit
from .const import (
    CHAR_ACTIVE,
    CHAR_COOLING_THRESHOLD_TEMPERATURE,
    CHAR_CURRENT_HEATER_COOLER_STATE,
    CHAR_CURRENT_HUMIDITY,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_HEATING_THRESHOLD_TEMPERATURE,
    CHAR_NAME,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_HEATER_COOLER_STATE,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
    SERV_HEATER_COOLER,
    SERV_HUMIDITY_SENSOR,
)

_LOGGER = logging.getLogger(__name__)

# HomeKit CurrentHeaterCoolerState values (per HomeKit spec)
HC_INACTIVE, HC_IDLE, HC_HEATING, HC_COOLING = range(4)

# HomeKit TargetHeaterCoolerState valid values: Auto=0, Heat=1, Cool=2
HC_TARGET_AUTO, HC_TARGET_HEAT, HC_TARGET_COOL = range(3)

# Off is intentionally not mapped: when the entity is off the target
# characteristic keeps the last active mode so it stays in sync with
# _last_known_mode, which is what turning Active back on restores.
HC_HASS_TO_HOMEKIT_TARGET = {
    HVACMode.HEAT: HC_TARGET_HEAT,
    HVACMode.COOL: HC_TARGET_COOL,
    HVACMode.HEAT_COOL: HC_TARGET_AUTO,
    HVACMode.AUTO: HC_TARGET_AUTO,
}

# HomeKit's CurrentHeaterCoolerState has no drying or fan-only value. Those
# actions map to Cooling rather than Idle so the tile still shows the unit is
# doing something, which also matches the Thermostat's action mapping.
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

# Hysteresis band in Celsius used when the entity omits hvac_action
ACTION_HYSTERESIS = 0.25


@TYPES.register("HeaterCooler")
class HeaterCooler(HomeKitClimateAccessory):
    """Generate a HeaterCooler accessory for a climate entity."""

    # Configured only when the entity accepts a target temperature.
    char_cool: Characteristic
    char_heat: Characteristic

    # Configured only when the entity reports a current humidity.
    char_current_humidity: Characteristic

    def __init__(self, *args: Any) -> None:
        """Initialize a HeaterCooler accessory object."""
        super().__init__(*args)

        state = self.hass.states.get(self.entity_id)
        assert state
        attributes = state.attributes
        features = attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # The thresholds double as the setpoints, so only expose them when the
        # entity accepts a target temperature; a fan/dry-only entity otherwise
        # gets sliders that dispatch set_temperature it cannot honor.
        self._has_thresholds = bool(
            features
            & (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
        )

        hvac_modes = attributes.get(ATTR_HVAC_MODES, [])
        current_mode = try_parse_enum(HVACMode, state.state)

        self._supports_off = HVACMode.OFF in hvac_modes
        supports_auto = HVACMode.AUTO in hvac_modes or current_mode == HVACMode.AUTO
        supports_heat_cool = (
            HVACMode.HEAT_COOL in hvac_modes or current_mode == HVACMode.HEAT_COOL
        )

        # Only expose the targets the entity actually supports so HomeKit does
        # not offer a mode the climate service would reject. Auto is backed by
        # a range mode, preferring AUTO over HEAT_COOL.
        self._hk_to_ha_target: dict[int, HVACMode] = {}
        if HVACMode.HEAT in hvac_modes:
            self._hk_to_ha_target[HC_TARGET_HEAT] = HVACMode.HEAT
        if HVACMode.COOL in hvac_modes:
            self._hk_to_ha_target[HC_TARGET_COOL] = HVACMode.COOL
        if supports_auto:
            self._hk_to_ha_target[HC_TARGET_AUTO] = HVACMode.AUTO
        elif supports_heat_cool:
            self._hk_to_ha_target[HC_TARGET_AUTO] = HVACMode.HEAT_COOL
        if not self._hk_to_ha_target:
            # Entities exposing neither heat, cool, nor a range mode (e.g.
            # fan-only) still need a valid target; map Auto to the first mode the
            # entity actually supports so the control does something. A degenerate
            # off-only entity has no active mode, so fall back to off rather than
            # an unsupported Auto.
            fallback_mode = next(
                (mode for mode in hvac_modes if mode != HVACMode.OFF), HVACMode.OFF
            )
            self._hk_to_ha_target[HC_TARGET_AUTO] = fallback_mode

        chars = [
            CHAR_ACTIVE,
            CHAR_CURRENT_HEATER_COOLER_STATE,
            CHAR_TARGET_HEATER_COOLER_STATE,
            CHAR_CURRENT_TEMPERATURE,
        ]
        if self._has_thresholds:
            chars.extend(
                (
                    CHAR_COOLING_THRESHOLD_TEMPERATURE,
                    CHAR_HEATING_THRESHOLD_TEMPERATURE,
                )
            )

        # Fan/swing modes are detected in the base class; only advertise the
        # characteristics when the entity exposes predefined modes.
        if self.ordered_fan_speeds:
            chars.append(CHAR_ROTATION_SPEED)
        if self.swing_on_mode is not None:
            chars.append(CHAR_SWING_MODE)

        serv = self.add_preload_service(SERV_HEATER_COOLER, chars)
        self.set_primary_service(serv)

        self.char_active = serv.configure_char(CHAR_ACTIVE, value=0)
        self.char_current_state = serv.configure_char(
            CHAR_CURRENT_HEATER_COOLER_STATE, value=HC_INACTIVE
        )
        target_valid_values = {
            ha_mode: hk_state for hk_state, ha_mode in self._hk_to_ha_target.items()
        }
        if HC_TARGET_AUTO in self._hk_to_ha_target:
            default_target = HC_TARGET_AUTO
        else:
            default_target = next(iter(self._hk_to_ha_target))
        self.char_target_state = self._configure_target_mode_char(
            serv, CHAR_TARGET_HEATER_COOLER_STATE, default_target, target_valid_values
        )
        self._configure_current_temperature_char(serv)

        if self._has_thresholds:
            min_temp_hk, max_temp_hk = self.get_temperature_range(state)
            temp_properties = {
                PROP_MIN_VALUE: min_temp_hk,
                PROP_MAX_VALUE: max_temp_hk,
                # We do not set PROP_MIN_STEP here and instead use the HomeKit
                # default of 0.1 in order to have enough precision to convert
                # temperature units and avoid setting 73F resulting in 74F
            }
            # Placeholder value within the configured range; async_update_state
            # overwrites it from the entity immediately.
            default_temp = min(max(21.0, min_temp_hk), max_temp_hk)
            self.char_cool = serv.configure_char(
                CHAR_COOLING_THRESHOLD_TEMPERATURE,
                value=default_temp,
                properties=temp_properties,
            )
            self.char_heat = serv.configure_char(
                CHAR_HEATING_THRESHOLD_TEMPERATURE,
                value=default_temp,
                properties=temp_properties,
            )

        if self.ordered_fan_speeds:
            self.char_speed = serv.configure_char(
                CHAR_ROTATION_SPEED,
                value=100,
                properties={PROP_MIN_STEP: 100 / len(self.ordered_fan_speeds)},
            )
        if self.swing_on_mode is not None:
            self.char_swing = serv.configure_char(CHAR_SWING_MODE, value=0)

        # The Heater Cooler service has no humidity characteristic, so surface a
        # reported current humidity through a linked humidity sensor. Like the
        # Thermostat, this is decided once at setup and not a reload attribute:
        # current humidity changes on every update, so reloading on it would
        # thrash the accessory.
        self._has_humidity = ATTR_CURRENT_HUMIDITY in attributes
        if self._has_humidity:
            humidity_serv = self.add_preload_service(SERV_HUMIDITY_SENSOR, CHAR_NAME)
            serv.add_linked_service(humidity_serv)
            self.char_current_humidity = humidity_serv.configure_char(
                CHAR_CURRENT_HUMIDITY, value=50
            )

        # Fall back to the displayed target mode so turning Active on for a device
        # that was off at startup activates the mode HomeKit is showing rather than
        # an arbitrary one.
        self._last_known_mode: HVACMode
        if current_mode and current_mode != HVACMode.OFF:
            self._last_known_mode = current_mode
        else:
            self._last_known_mode = self._hk_to_ha_target[default_target]

        self.async_update_state(state)

        # A single service-level callback batches every characteristic write.
        serv.setter_callback = self._set_chars

    def _set_chars(self, char_values: dict[str, Any]) -> None:
        """Handle writes to multiple HeaterCooler characteristics at once."""
        _LOGGER.debug("HeaterCooler _set_chars: %s", char_values)
        service_calls: list[tuple[str, dict[str, Any]]] = []
        current_state = self.hass.states.get(self.entity_id)

        # Active/mode changes are handled first as they gate the others.
        self._handle_active_mode_changes(char_values, service_calls, current_state)
        # Temperature and fan/swing writes are meaningless when turning off.
        active_on = char_values.get(CHAR_ACTIVE) != 0
        if active_on:
            self._handle_temperature_changes(char_values, service_calls, current_state)

        for service_name, service_data in service_calls:
            self.async_call_service(
                CLIMATE_DOMAIN,
                service_name,
                {ATTR_ENTITY_ID: self.entity_id, **service_data},
            )

        # Fan and swing are applied after the mode/temperature writes so the
        # calls are dispatched in the intended order.
        if active_on:
            self._handle_fan_swing_changes(char_values)

    def _handle_active_mode_changes(
        self,
        char_values: dict[str, Any],
        service_calls: list[tuple[str, dict[str, Any]]],
        current_state: State | None,
    ) -> None:
        """Handle active and mode changes."""
        active = char_values.get(CHAR_ACTIVE)
        target_mode = char_values.get(CHAR_TARGET_HEATER_COOLER_STATE)

        if active is None and target_mode is None:
            return

        if active == 0:
            # climate.turn_off raises for entities without an OFF mode; set the
            # OFF mode directly and only when it is supported, like the thermostat.
            if self._supports_off:
                service_calls.append(
                    (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.OFF})
                )
            else:
                _LOGGER.debug(
                    "%s: Ignoring off request; entity has no off mode",
                    self.entity_id,
                )
        elif target_mode is not None:
            if hass_mode := self._hk_to_ha_target.get(target_mode):
                service_calls.append(
                    (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: hass_mode})
                )
                self._last_known_mode = hass_mode
        elif active == 1:
            currently_active = current_state is not None and (
                current_state.state
                not in (HVACMode.OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)
            )
            if not currently_active:
                service_calls.append(
                    (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: self._last_known_mode})
                )

    def _handle_temperature_changes(
        self,
        char_values: dict[str, Any],
        service_calls: list[tuple[str, dict[str, Any]]],
        current_state: State | None,
    ) -> None:
        """Handle temperature changes."""
        cooling_temp = char_values.get(CHAR_COOLING_THRESHOLD_TEMPERATURE)
        heating_temp = char_values.get(CHAR_HEATING_THRESHOLD_TEMPERATURE)

        if cooling_temp is None and heating_temp is None:
            return

        supports_dual_temp = current_state is not None and (
            ATTR_TARGET_TEMP_HIGH in current_state.attributes
            or ATTR_TARGET_TEMP_LOW in current_state.attributes
        )

        if supports_dual_temp:
            service_calls.append(
                (
                    SERVICE_SET_TEMPERATURE,
                    self._dual_setpoint_params(
                        self.char_cool, self.char_heat, cooling_temp, heating_temp
                    ),
                )
            )
        else:
            self._handle_single_temp_changes(
                service_calls, cooling_temp, heating_temp, current_state
            )

    def _handle_single_temp_changes(
        self,
        service_calls: list[tuple[str, dict[str, Any]]],
        cooling_temp: float | None,
        heating_temp: float | None,
        current_state: State | None,
    ) -> None:
        """Handle temperature changes for single-temperature entities."""
        if not current_state:
            return

        # For a single setpoint the active mode decides which threshold is the
        # setpoint; Cool uses the cooling side and Heat the heating side, so a
        # write to the other side is ignored. Range and other modes fall back to
        # whichever threshold moved, and Auto picks the one furthest from the
        # current setpoint.
        current_mode = current_state.state
        selected_temp = None
        if current_mode == HVACMode.COOL:
            selected_temp = cooling_temp
        elif current_mode == HVACMode.HEAT:
            selected_temp = heating_temp
        elif (
            current_mode == HVACMode.HEAT_COOL
            and cooling_temp is not None
            and heating_temp is not None
        ):
            # Pick whichever threshold moved further from the entity's existing
            # target setpoint. The thresholds are in HomeKit units, so convert
            # the target setpoint before comparing.
            target_temp = current_state.attributes.get(ATTR_TEMPERATURE)
            if target_temp is None:
                selected_temp = heating_temp
            else:
                target_temp_hk = self._temperature_to_homekit(target_temp)
                if abs(cooling_temp - target_temp_hk) > abs(
                    heating_temp - target_temp_hk
                ):
                    selected_temp = cooling_temp
                else:
                    selected_temp = heating_temp
        elif cooling_temp is not None:
            selected_temp = cooling_temp
        elif heating_temp is not None:
            selected_temp = heating_temp

        if selected_temp is not None:
            ha_temp = self._temperature_to_states(selected_temp)
            service_calls.append((SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: ha_temp}))

    def _handle_fan_swing_changes(self, char_values: dict[str, Any]) -> None:
        """Handle fan speed and swing mode changes."""
        if CHAR_ROTATION_SPEED in char_values:
            self._set_fan_speed(char_values[CHAR_ROTATION_SPEED])
        if CHAR_SWING_MODE in char_values:
            self._set_swing_mode(char_values[CHAR_SWING_MODE])

    def _hk_target_mode(self, mode: HVACMode | None) -> int | None:
        """Map HA hvac_mode to a HomeKit target heater-cooler state."""
        if mode is None:
            return None

        # HomeKit's HeaterCooler target only has Auto/Heat/Cool, so modes like
        # dry and fan_only have no representation; they are intentionally
        # collapsed to the Auto target (see the fallback in __init__) and cannot
        # be selected or reflected individually from the Home app.
        hk_value = HC_HASS_TO_HOMEKIT_TARGET.get(mode)
        if hk_value is not None and hk_value in self._hk_to_ha_target:
            return hk_value
        return None

    @callback
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update state without rechecking the device features."""
        attributes = new_state.attributes
        current_mode = try_parse_enum(HVACMode, new_state.state)
        if current_mode and current_mode != HVACMode.OFF:
            self._last_known_mode = current_mode

        if (tgt := self._hk_target_mode(current_mode)) is not None:
            self.char_target_state.set_value(tgt)

        if new_state.state in (HVACMode.OFF, STATE_UNAVAILABLE, STATE_UNKNOWN):
            # An off or unavailable entity is inactive, not idle.
            self.char_active.set_value(0)
            self.char_current_state.set_value(HC_INACTIVE)
        else:
            self.char_active.set_value(1)
            action = attributes.get(ATTR_HVAC_ACTION) or self._derive_action(
                new_state, current_mode
            )
            self.char_current_state.set_value(
                HC_HASS_TO_HOMEKIT_ACTION.get(action, HC_INACTIVE)
            )

        self._update_current_temperature_char(new_state)
        self._update_temperature_thresholds(new_state)
        if self._has_humidity and isinstance(
            (humidity := attributes.get(ATTR_CURRENT_HUMIDITY)), (int, float)
        ):
            self.char_current_humidity.set_value(humidity)
        # The base char updaters no-op when the entity exposes no fan/swing.
        self._update_fan_speed_char(attributes)
        self._update_swing_char(attributes)

    def _update_temperature_thresholds(self, state: State) -> None:
        """Update HomeKit temperature thresholds based on HA state."""
        if not self._has_thresholds:
            return
        attributes = state.attributes
        supports_dual_temp = (
            ATTR_TARGET_TEMP_HIGH in attributes or ATTR_TARGET_TEMP_LOW in attributes
        )

        if supports_dual_temp:
            self._update_temperature_char(self.char_cool, state, ATTR_TARGET_TEMP_HIGH)
            self._update_temperature_char(self.char_heat, state, ATTR_TARGET_TEMP_LOW)
        elif (
            target_temp := temperature_attribute_to_homekit(
                state, ATTR_TEMPERATURE, self._unit
            )
        ) is not None:
            self.char_cool.set_value(target_temp)
            self.char_heat.set_value(target_temp)

    def _derive_action(self, state: State, mode: HVACMode | None) -> HVACAction:
        """Infer heating / cooling when integration omits hvac_action."""
        attributes = state.attributes
        cur = attributes.get(ATTR_CURRENT_TEMPERATURE)
        if cur is None or mode is None:
            return HVACAction.IDLE

        # Resolve the cool-above and heat-below setpoints for the active mode.
        # Range modes have independent thresholds; single-target modes only
        # drive one side. Any other mode (e.g. dry, fan_only) stays idle.
        if mode in (HVACMode.HEAT_COOL, HVACMode.AUTO):
            cool_above = attributes.get(ATTR_TARGET_TEMP_HIGH)
            heat_below = attributes.get(ATTR_TARGET_TEMP_LOW)
        elif mode == HVACMode.COOL:
            cool_above = attributes.get(ATTR_TEMPERATURE)
            heat_below = None
        elif mode == HVACMode.HEAT:
            cool_above = None
            heat_below = attributes.get(ATTR_TEMPERATURE)
        else:
            return HVACAction.IDLE

        # Compare in Celsius so the hysteresis band is unit independent.
        cur_c = self._temperature_to_homekit(cur)
        if (
            cool_above is not None
            and cur_c > self._temperature_to_homekit(cool_above) + ACTION_HYSTERESIS
        ):
            return HVACAction.COOLING
        if (
            heat_below is not None
            and cur_c < self._temperature_to_homekit(heat_below) - ACTION_HYSTERESIS
        ):
            return HVACAction.HEATING
        return HVACAction.IDLE
