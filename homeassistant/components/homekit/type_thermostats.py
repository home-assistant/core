"""Class to hold all thermostat accessories."""

import logging
from typing import Any, override

from pyhap.const import CATEGORY_THERMOSTAT

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_ON,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE as SERVICE_SET_HVAC_MODE_THERMOSTAT,
    SERVICE_SET_TEMPERATURE as SERVICE_SET_TEMPERATURE_THERMOSTAT,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.water_heater import (
    ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE as SERVICE_SET_TEMPERATURE_WATER_HEATER,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import State, callback
from homeassistant.util.enum import try_parse_enum

from .accessories import TYPES, HomeAccessory
from .climate_base import HomeKitClimateAccessory
from .climate_util import (
    get_temperature_range_from_state,
    temperature_attribute_to_homekit,
)
from .const import (
    CHAR_COOLING_THRESHOLD_TEMPERATURE,
    CHAR_CURRENT_FAN_STATE,
    CHAR_CURRENT_HEATING_COOLING,
    CHAR_CURRENT_HUMIDITY,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_HEATING_THRESHOLD_TEMPERATURE,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_FAN_STATE,
    CHAR_TARGET_HEATING_COOLING,
    CHAR_TARGET_HUMIDITY,
    CHAR_TARGET_TEMPERATURE,
    CHAR_TEMP_DISPLAY_UNITS,
    DEFAULT_MAX_TEMP_WATER_HEATER,
    DEFAULT_MIN_TEMP_WATER_HEATER,
    PROP_MAX_VALUE,
    PROP_MIN_VALUE,
    SERV_THERMOSTAT,
)
from .util import get_min_max, temperature_to_states

_LOGGER = logging.getLogger(__name__)

DEFAULT_HVAC_MODES = [
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.HEAT_COOL,
    HVACMode.OFF,
]

HC_HOMEKIT_VALID_MODES_WATER_HEATER = {"Heat": 1}
UNIT_HASS_TO_HOMEKIT = {UnitOfTemperature.CELSIUS: 0, UnitOfTemperature.FAHRENHEIT: 1}

HC_HEAT_COOL_OFF = 0
HC_HEAT_COOL_HEAT = 1
HC_HEAT_COOL_COOL = 2
HC_HEAT_COOL_AUTO = 3

HC_HEAT_COOL_PREFER_HEAT = [
    HC_HEAT_COOL_AUTO,
    HC_HEAT_COOL_HEAT,
    HC_HEAT_COOL_COOL,
    HC_HEAT_COOL_OFF,
]

HC_HEAT_COOL_PREFER_COOL = [
    HC_HEAT_COOL_AUTO,
    HC_HEAT_COOL_COOL,
    HC_HEAT_COOL_HEAT,
    HC_HEAT_COOL_OFF,
]

HC_MIN_TEMP = 10
HC_MAX_TEMP = 38

UNIT_HOMEKIT_TO_HASS = {c: s for s, c in UNIT_HASS_TO_HOMEKIT.items()}
HC_HASS_TO_HOMEKIT = {
    HVACMode.OFF: HC_HEAT_COOL_OFF,
    HVACMode.HEAT: HC_HEAT_COOL_HEAT,
    HVACMode.COOL: HC_HEAT_COOL_COOL,
    HVACMode.AUTO: HC_HEAT_COOL_AUTO,
    HVACMode.HEAT_COOL: HC_HEAT_COOL_AUTO,
    HVACMode.DRY: HC_HEAT_COOL_COOL,
    HVACMode.FAN_ONLY: HC_HEAT_COOL_COOL,
}
HC_HOMEKIT_TO_HASS = {c: s for s, c in HC_HASS_TO_HOMEKIT.items()}

HC_HASS_TO_HOMEKIT_ACTION = {
    HVACAction.OFF: HC_HEAT_COOL_OFF,
    HVACAction.IDLE: HC_HEAT_COOL_OFF,
    HVACAction.HEATING: HC_HEAT_COOL_HEAT,
    HVACAction.COOLING: HC_HEAT_COOL_COOL,
    HVACAction.DRYING: HC_HEAT_COOL_COOL,
    HVACAction.FAN: HC_HEAT_COOL_COOL,
    HVACAction.PREHEATING: HC_HEAT_COOL_HEAT,
    HVACAction.DEFROSTING: HC_HEAT_COOL_HEAT,
}


def _hk_hvac_mode_from_state(state: State) -> int | None:
    """Return the equivalent HomeKit HVAC mode for a given state."""
    if (current_state := state.state) in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    if not (hvac_mode := try_parse_enum(HVACMode, current_state)):
        _LOGGER.error(
            "%s: Received invalid HVAC mode: %s", state.entity_id, state.state
        )
        return None
    return HC_HASS_TO_HOMEKIT.get(hvac_mode)


@TYPES.register("Thermostat")
class Thermostat(HomeKitClimateAccessory):
    """Generate a Thermostat accessory for a climate."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Thermostat accessory object."""
        super().__init__(*args)
        state = self.hass.states.get(self.entity_id)
        assert state
        hc_min_temp, hc_max_temp = self.get_temperature_range(state)
        # The common climate reload attributes are added by the base class.
        self._reload_on_change_attrs.append(ATTR_MIN_HUMIDITY)

        # Add additional characteristics if auto mode is supported
        self.chars: list[str] = []

        attributes = state.attributes
        min_humidity, _ = get_min_max(
            attributes.get(ATTR_MIN_HUMIDITY, DEFAULT_MIN_HUMIDITY),
            attributes.get(ATTR_MAX_HUMIDITY, DEFAULT_MAX_HUMIDITY),
        )
        features = attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
            self.chars.extend(
                (CHAR_COOLING_THRESHOLD_TEMPERATURE, CHAR_HEATING_THRESHOLD_TEMPERATURE)
            )

        if (
            ATTR_CURRENT_HUMIDITY in attributes
            or features & ClimateEntityFeature.TARGET_HUMIDITY
        ):
            self.chars.append(CHAR_CURRENT_HUMIDITY)

        if features & ClimateEntityFeature.TARGET_HUMIDITY:
            self.chars.append(CHAR_TARGET_HUMIDITY)

        serv_thermostat = self.add_preload_service(SERV_THERMOSTAT, self.chars)

        # Current mode characteristics
        self.char_current_heat_cool = serv_thermostat.configure_char(
            CHAR_CURRENT_HEATING_COOLING, value=0
        )

        self._configure_hvac_modes(state)
        self.char_target_heat_cool = self._configure_target_mode_char(
            serv_thermostat,
            CHAR_TARGET_HEATING_COOLING,
            list(self.hc_homekit_to_hass)[0],
            self.hc_hass_to_homekit,
        )

        self._configure_current_temperature_char(serv_thermostat)

        self.char_target_temp = serv_thermostat.configure_char(
            CHAR_TARGET_TEMPERATURE,
            value=21.0,
            # We do not set PROP_MIN_STEP here and instead use the HomeKit
            # default of 0.1 in order to have enough precision to convert
            # temperature units and avoid setting to 73F will result in 74F
            properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
        )

        # Display units characteristic
        self.char_display_units = serv_thermostat.configure_char(
            CHAR_TEMP_DISPLAY_UNITS, value=0
        )

        # If the device supports it: high and low temperature characteristics
        self.char_cooling_thresh_temp = None
        self.char_heating_thresh_temp = None
        if CHAR_COOLING_THRESHOLD_TEMPERATURE in self.chars:
            self.char_cooling_thresh_temp = serv_thermostat.configure_char(
                CHAR_COOLING_THRESHOLD_TEMPERATURE,
                value=23.0,
                # We do not set PROP_MIN_STEP here and instead use the HomeKit
                # default of 0.1 in order to have enough precision to convert
                # temperature units and avoid setting to 73F will result in 74F
                properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
            )
        if CHAR_HEATING_THRESHOLD_TEMPERATURE in self.chars:
            self.char_heating_thresh_temp = serv_thermostat.configure_char(
                CHAR_HEATING_THRESHOLD_TEMPERATURE,
                value=19.0,
                # We do not set PROP_MIN_STEP here and instead use the HomeKit
                # default of 0.1 in order to have enough precision to convert
                # temperature units and avoid setting to 73F will result in 74F
                properties={PROP_MIN_VALUE: hc_min_temp, PROP_MAX_VALUE: hc_max_temp},
            )
        self.char_target_humidity = None
        if CHAR_TARGET_HUMIDITY in self.chars:
            self.char_target_humidity = serv_thermostat.configure_char(
                CHAR_TARGET_HUMIDITY,
                value=50,
                # We do not set a max humidity because
                # homekit currently has a bug that will show the lower bound
                # shifted upwards.  For example if you have a max humidity
                # of 80% homekit will give you the options 20%-100% instead
                # of 0-80%
                properties={PROP_MIN_VALUE: min_humidity},
            )
        self.char_current_humidity = None
        if CHAR_CURRENT_HUMIDITY in self.chars:
            self.char_current_humidity = serv_thermostat.configure_char(
                CHAR_CURRENT_HUMIDITY, value=50
            )

        # Fan/swing modes are detected in the base class.
        if self.ordered_fan_speeds:
            self.fan_chars.append(CHAR_ROTATION_SPEED)

        if FAN_AUTO in self.fan_modes and (
            FAN_ON in self.fan_modes or self.ordered_fan_speeds
        ):
            self.fan_chars.append(CHAR_TARGET_FAN_STATE)

        if self.swing_on_mode:
            self.fan_chars.append(CHAR_SWING_MODE)

        if self.fan_chars:
            if attributes.get(ATTR_HVAC_ACTION) is not None:
                self.fan_chars.append(CHAR_CURRENT_FAN_STATE)
            self._configure_fan_service(serv_thermostat)

        # Every service exists now, so they all get an explicit primary
        # flag; without one the Home app can pick its own tile service.
        self.set_primary_service(serv_thermostat)

        self.async_update_state(state)

        serv_thermostat.setter_callback = self._set_chars

    def _set_chars(self, char_values: dict[str, Any]) -> None:
        _LOGGER.debug("Thermostat _set_chars: %s", char_values)
        events = []
        params: dict[str, Any] = {ATTR_ENTITY_ID: self.entity_id}
        service = None
        state = self.hass.states.get(self.entity_id)
        assert state
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        homekit_hvac_mode = _hk_hvac_mode_from_state(state)
        # Homekit will reset the mode when VIEWING the temp
        # Ignore it if its the same mode
        if (
            CHAR_TARGET_HEATING_COOLING in char_values
            and char_values[CHAR_TARGET_HEATING_COOLING] != homekit_hvac_mode
        ):
            target_hc = char_values[CHAR_TARGET_HEATING_COOLING]
            if target_hc not in self.hc_homekit_to_hass:
                # If the target heating cooling state we want does not
                # exist on the device, we have to sort it out
                # based on the current and target temperature since
                # siri will always send HC_HEAT_COOL_AUTO in this case
                # and hope for the best.
                hc_target_temp = char_values.get(CHAR_TARGET_TEMPERATURE)
                hc_current_temp = temperature_attribute_to_homekit(
                    state, ATTR_CURRENT_TEMPERATURE, self._unit
                )
                hc_fallback_order = HC_HEAT_COOL_PREFER_HEAT
                if (
                    hc_target_temp is not None
                    and hc_current_temp is not None
                    and hc_target_temp < hc_current_temp
                ):
                    hc_fallback_order = HC_HEAT_COOL_PREFER_COOL
                for hc_fallback in hc_fallback_order:
                    if hc_fallback in self.hc_homekit_to_hass:
                        _LOGGER.debug(
                            (
                                "Siri requested target mode: %s and the device does not"
                                " support, falling back to %s"
                            ),
                            target_hc,
                            hc_fallback,
                        )
                        self.char_target_heat_cool.value = target_hc = hc_fallback
                        break

            params[ATTR_HVAC_MODE] = self.hc_homekit_to_hass[target_hc]
            events.append(
                f"{CHAR_TARGET_HEATING_COOLING} to"
                f" {char_values[CHAR_TARGET_HEATING_COOLING]}"
            )
            # Many integrations do not actually implement `hvac_mode` for the
            # `SERVICE_SET_TEMPERATURE_THERMOSTAT` service so we
            # made a call to `SERVICE_SET_HVAC_MODE_THERMOSTAT`
            # before calling `SERVICE_SET_TEMPERATURE_THERMOSTAT`
            # to ensure the device is in the right mode before setting the temp.
            self.async_call_service(
                CLIMATE_DOMAIN,
                SERVICE_SET_HVAC_MODE_THERMOSTAT,
                params.copy(),
                ", ".join(events),
            )

        if CHAR_TARGET_TEMPERATURE in char_values:
            hc_target_temp = char_values[CHAR_TARGET_TEMPERATURE]
            if features & ClimateEntityFeature.TARGET_TEMPERATURE:
                service = SERVICE_SET_TEMPERATURE_THERMOSTAT
                temperature = self._temperature_to_states(hc_target_temp)
                events.append(
                    f"{CHAR_TARGET_TEMPERATURE} to"
                    f" {char_values[CHAR_TARGET_TEMPERATURE]}°C"
                )
                params[ATTR_TEMPERATURE] = temperature
            elif features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
                # Homekit will send us a target temperature
                # even if the device does not support it
                _LOGGER.debug(
                    "Homekit requested target temp: %s and the device does not support",
                    hc_target_temp,
                )
                if (
                    homekit_hvac_mode == HC_HEAT_COOL_HEAT
                    and CHAR_HEATING_THRESHOLD_TEMPERATURE not in char_values
                ):
                    char_values[CHAR_HEATING_THRESHOLD_TEMPERATURE] = hc_target_temp
                if (
                    homekit_hvac_mode == HC_HEAT_COOL_COOL
                    and CHAR_COOLING_THRESHOLD_TEMPERATURE not in char_values
                ):
                    char_values[CHAR_COOLING_THRESHOLD_TEMPERATURE] = hc_target_temp

        if (
            CHAR_HEATING_THRESHOLD_TEMPERATURE in char_values
            or CHAR_COOLING_THRESHOLD_TEMPERATURE in char_values
        ):
            assert self.char_cooling_thresh_temp
            assert self.char_heating_thresh_temp
            service = SERVICE_SET_TEMPERATURE_THERMOSTAT
            new_high = char_values.get(CHAR_COOLING_THRESHOLD_TEMPERATURE)
            new_low = char_values.get(CHAR_HEATING_THRESHOLD_TEMPERATURE)
            if new_high is not None:
                events.append(f"{CHAR_COOLING_THRESHOLD_TEMPERATURE} to {new_high}°C")
            if new_low is not None:
                events.append(f"{CHAR_HEATING_THRESHOLD_TEMPERATURE} to {new_low}°C")
            # A device without TARGET_TEMPERATURE can send an inverted pair.
            params.update(
                self._dual_setpoint_params(
                    self.char_cooling_thresh_temp,
                    self.char_heating_thresh_temp,
                    new_high,
                    new_low,
                )
            )

        if service:
            self.async_call_service(
                CLIMATE_DOMAIN,
                service,
                params,
                ", ".join(events),
            )

        if CHAR_TARGET_HUMIDITY in char_values:
            self.set_target_humidity(char_values[CHAR_TARGET_HUMIDITY])

    def _configure_hvac_modes(self, state: State) -> None:
        """Configure target mode characteristics."""
        # This cannot be none OR an empty list
        hc_modes = state.attributes.get(ATTR_HVAC_MODES) or DEFAULT_HVAC_MODES
        # Determine available modes for this entity,
        # Prefer HEAT_COOL over AUTO and COOL over FAN_ONLY, DRY
        #
        # HEAT_COOL is preferred over auto because HomeKit Accessory Protocol describes
        # heating or cooling comes on to maintain a target temp which is closest to
        # the Home Assistant spec
        #
        # HVACMode.HEAT_COOL: The device supports heating/cooling to a range
        self.hc_homekit_to_hass = {
            c: s
            for s, c in HC_HASS_TO_HOMEKIT.items()
            if (
                s in hc_modes
                and not (
                    (s == HVACMode.AUTO and HVACMode.HEAT_COOL in hc_modes)
                    or (
                        s in (HVACMode.DRY, HVACMode.FAN_ONLY)
                        and HVACMode.COOL in hc_modes
                    )
                )
            )
        }
        self.hc_hass_to_homekit = {k: v for v, k in self.hc_homekit_to_hass.items()}

    def set_target_humidity(self, value: float) -> None:
        """Set target humidity to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set target humidity to %d", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_HUMIDITY: value}
        self.async_call_service(
            CLIMATE_DOMAIN, SERVICE_SET_HUMIDITY, params, f"{value}{PERCENTAGE}"
        )

    @callback
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update state without rechecking the device features."""
        attributes = new_state.attributes
        features = attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # Update target operation mode FIRST
        if (homekit_hvac_mode := _hk_hvac_mode_from_state(new_state)) is not None:
            if homekit_hvac_mode in self.hc_homekit_to_hass:
                self.char_target_heat_cool.set_value(homekit_hvac_mode)
            else:
                _LOGGER.error(
                    (
                        "Cannot map hvac target mode: %s to homekit as only %s modes"
                        " are supported"
                    ),
                    new_state.state,
                    self.hc_homekit_to_hass,
                )

        # Set current operation mode for supported thermostats
        if hvac_action := attributes.get(ATTR_HVAC_ACTION):
            self.char_current_heat_cool.set_value(
                HC_HASS_TO_HOMEKIT_ACTION.get(hvac_action, HC_HEAT_COOL_OFF)
            )

        self._update_current_temperature_char(new_state)

        # Update current humidity
        if CHAR_CURRENT_HUMIDITY in self.chars:
            assert self.char_current_humidity
            current_humdity = attributes.get(ATTR_CURRENT_HUMIDITY)
            if isinstance(current_humdity, (int, float)):
                self.char_current_humidity.set_value(current_humdity)

        # Update target humidity
        if CHAR_TARGET_HUMIDITY in self.chars:
            assert self.char_target_humidity
            target_humdity = attributes.get(ATTR_HUMIDITY)
            if isinstance(target_humdity, (int, float)):
                self.char_target_humidity.set_value(target_humdity)

        # Update threshold temperatures if the characteristics exist
        if self.char_cooling_thresh_temp:
            self._update_temperature_char(
                self.char_cooling_thresh_temp, new_state, ATTR_TARGET_TEMP_HIGH
            )
        if self.char_heating_thresh_temp:
            self._update_temperature_char(
                self.char_heating_thresh_temp, new_state, ATTR_TARGET_TEMP_LOW
            )

        # Update target temperature
        target_temp = temperature_attribute_to_homekit(
            new_state, ATTR_TEMPERATURE, self._unit
        )
        if (
            target_temp is None
            and features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        ):
            # Homekit expects a target temperature
            # even if the device does not support it
            hc_hvac_mode = self.char_target_heat_cool.value
            if hc_hvac_mode == HC_HEAT_COOL_HEAT:
                temp_low = attributes.get(ATTR_TARGET_TEMP_LOW)
                if isinstance(temp_low, (int, float)):
                    target_temp = self._temperature_to_homekit(temp_low)
            elif hc_hvac_mode == HC_HEAT_COOL_COOL:
                temp_high = attributes.get(ATTR_TARGET_TEMP_HIGH)
                if isinstance(temp_high, (int, float)):
                    target_temp = self._temperature_to_homekit(temp_high)
        if target_temp:
            self.char_target_temp.set_value(target_temp)

        # Update display units
        if self._unit and self._unit in UNIT_HASS_TO_HOMEKIT:
            unit = UNIT_HASS_TO_HOMEKIT[self._unit]
            self.char_display_units.set_value(unit)

        if self.fan_chars:
            self._async_update_fan_service(new_state)


@TYPES.register("WaterHeater")
class WaterHeater(HomeAccessory):
    """Generate a WaterHeater accessory for a water_heater."""

    def __init__(self, *args: Any) -> None:
        """Initialize a WaterHeater accessory object."""
        super().__init__(*args, category=CATEGORY_THERMOSTAT)
        self._reload_on_change_attrs.extend(
            (
                ATTR_MAX_TEMP,
                ATTR_MIN_TEMP,
                ATTR_OPERATION_LIST,
            )
        )
        self._unit = self.hass.config.units.temperature_unit
        state = self.hass.states.get(self.entity_id)
        assert state
        min_temp, max_temp = self.get_temperature_range(state)

        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        operation_list = state.attributes.get(ATTR_OPERATION_LIST) or []
        self._supports_on_off = bool(features & WaterHeaterEntityFeature.ON_OFF)
        self._supports_operation_mode = bool(
            features & WaterHeaterEntityFeature.OPERATION_MODE
        )
        self._off_mode_available = self._supports_on_off or (
            self._supports_operation_mode and STATE_OFF in operation_list
        )

        valid_modes = dict(HC_HOMEKIT_VALID_MODES_WATER_HEATER)
        if self._off_mode_available:
            valid_modes["Off"] = HC_HEAT_COOL_OFF

        serv_thermostat = self.add_preload_service(SERV_THERMOSTAT)

        self.char_current_heat_cool = serv_thermostat.configure_char(
            CHAR_CURRENT_HEATING_COOLING, value=1
        )
        self.char_target_heat_cool = serv_thermostat.configure_char(
            CHAR_TARGET_HEATING_COOLING,
            value=1,
            setter_callback=self.set_heat_cool,
            valid_values=valid_modes,
        )

        self.char_current_temp = serv_thermostat.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=50.0
        )
        self.char_target_temp = serv_thermostat.configure_char(
            CHAR_TARGET_TEMPERATURE,
            value=50.0,
            # We do not set PROP_MIN_STEP here and instead use the HomeKit
            # default of 0.1 in order to have enough precision to convert
            # temperature units and avoid setting to 73F will result in 74F
            properties={PROP_MIN_VALUE: min_temp, PROP_MAX_VALUE: max_temp},
            setter_callback=self.set_target_temperature,
        )

        self.char_display_units = serv_thermostat.configure_char(
            CHAR_TEMP_DISPLAY_UNITS, value=0
        )

        self.async_update_state(state)

    def get_temperature_range(self, state: State) -> tuple[float, float]:
        """Return min and max temperature range."""
        return get_temperature_range_from_state(
            state,
            self._unit,
            DEFAULT_MIN_TEMP_WATER_HEATER,
            DEFAULT_MAX_TEMP_WATER_HEATER,
        )

    def set_heat_cool(self, value: int) -> None:
        """Change operation mode to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set heat-cool to %d", self.entity_id, value)
        params: dict[str, Any] = {ATTR_ENTITY_ID: self.entity_id}
        if value == HC_HEAT_COOL_OFF:
            if self._supports_on_off:
                self.async_call_service(
                    WATER_HEATER_DOMAIN, SERVICE_TURN_OFF, params, "off"
                )
            elif self._off_mode_available and self._supports_operation_mode:
                params[ATTR_OPERATION_MODE] = STATE_OFF
                self.async_call_service(
                    WATER_HEATER_DOMAIN,
                    SERVICE_SET_OPERATION_MODE,
                    params,
                    STATE_OFF,
                )
            else:
                self.char_target_heat_cool.set_value(HC_HEAT_COOL_HEAT)
        elif value == HC_HEAT_COOL_HEAT:
            if self._supports_on_off:
                self.async_call_service(
                    WATER_HEATER_DOMAIN, SERVICE_TURN_ON, params, "on"
                )
            elif self._off_mode_available and self._supports_operation_mode:
                state = self.hass.states.get(self.entity_id)
                if not state:
                    return
                current_operation_mode = state.attributes.get(ATTR_OPERATION_MODE)
                if current_operation_mode and current_operation_mode != STATE_OFF:
                    # Already in a non-off operation mode; do not change it.
                    return
                operation_list = state.attributes.get(ATTR_OPERATION_LIST) or []
                for mode in operation_list:
                    if mode != STATE_OFF:
                        params[ATTR_OPERATION_MODE] = mode
                        self.async_call_service(
                            WATER_HEATER_DOMAIN,
                            SERVICE_SET_OPERATION_MODE,
                            params,
                            mode,
                        )
                        break
        else:
            self.char_target_heat_cool.set_value(HC_HEAT_COOL_HEAT)

    def set_target_temperature(self, value: float) -> None:
        """Set target temperature to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set target temperature to %.1f°C", self.entity_id, value)
        temperature = temperature_to_states(value, self._unit)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_TEMPERATURE: temperature}
        self.async_call_service(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE_WATER_HEATER,
            params,
            f"{temperature}{self._unit}",
        )

    @callback
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update water_heater state after state change."""
        # Update current and target temperature
        target_temperature = temperature_attribute_to_homekit(
            new_state, ATTR_TEMPERATURE, self._unit
        )
        if target_temperature is not None:
            self.char_target_temp.set_value(target_temperature)

        current_temperature = temperature_attribute_to_homekit(
            new_state, ATTR_CURRENT_TEMPERATURE, self._unit
        )
        if current_temperature is not None:
            self.char_current_temp.set_value(current_temperature)

        # Update display units
        if self._unit and self._unit in UNIT_HASS_TO_HOMEKIT:
            unit = UNIT_HASS_TO_HOMEKIT[self._unit]
            self.char_display_units.set_value(unit)

        # Update target operation mode
        if new_state.state:
            if new_state.state == STATE_OFF and self._off_mode_available:
                self.char_target_heat_cool.set_value(HC_HEAT_COOL_OFF)
                self.char_current_heat_cool.set_value(HC_HEAT_COOL_OFF)
            else:
                self.char_target_heat_cool.set_value(HC_HEAT_COOL_HEAT)
                self.char_current_heat_cool.set_value(HC_HEAT_COOL_HEAT)
