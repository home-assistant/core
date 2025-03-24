"""Class to hold all thermostat accessories."""

import logging
from typing import Any

from pyhap.const import CATEGORY_THERMOSTAT

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_HUMIDITY,
    DEFAULT_MIN_TEMP,
    DOMAIN as DOMAIN_CLIMATE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    FAN_ON,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE as SERVICE_SET_HVAC_MODE_THERMOSTAT,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE as SERVICE_SET_TEMPERATURE_THERMOSTAT,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.water_heater import (
    DOMAIN as DOMAIN_WATER_HEATER,
    SERVICE_SET_TEMPERATURE as SERVICE_SET_TEMPERATURE_WATER_HEATER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import State, callback
from homeassistant.util.enum import try_parse_enum
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
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
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
    SERV_FANV2,
    SERV_THERMOSTAT,
)
from .util import get_min_max, temperature_to_homekit, temperature_to_states

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

ORDERED_FAN_SPEEDS = [FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH]
PRE_DEFINED_FAN_MODES = set(ORDERED_FAN_SPEEDS)
SWING_MODE_PREFERRED_ORDER = [SWING_ON, SWING_BOTH, SWING_HORIZONTAL, SWING_VERTICAL]
PRE_DEFINED_SWING_MODES = set(SWING_MODE_PREFERRED_ORDER)

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

FAN_STATE_INACTIVE = 0
FAN_STATE_IDLE = 1
FAN_STATE_ACTIVE = 2

HC_HASS_TO_HOMEKIT_FAN_STATE = {
    HVACAction.OFF: FAN_STATE_INACTIVE,
    HVACAction.IDLE: FAN_STATE_IDLE,
    HVACAction.HEATING: FAN_STATE_ACTIVE,
    HVACAction.COOLING: FAN_STATE_ACTIVE,
    HVACAction.DRYING: FAN_STATE_ACTIVE,
    HVACAction.FAN: FAN_STATE_ACTIVE,
}

HEAT_COOL_DEADBAND = 5


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
class Thermostat(HomeAccessory):
    """Generate a Thermostat accessory for a climate."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Thermostat accessory object."""
        super().__init__(*args, category=CATEGORY_THERMOSTAT)
        self._unit = self.hass.config.units.temperature_unit
        state = self.hass.states.get(self.entity_id)
        assert state
        hc_min_temp, hc_max_temp = self.get_temperature_range(state)
        self._reload_on_change_attrs.extend(
            (
                ATTR_MIN_HUMIDITY,
                ATTR_MAX_TEMP,
                ATTR_MIN_TEMP,
                ATTR_FAN_MODES,
                ATTR_HVAC_MODES,
            )
        )

        # Add additional characteristics if auto mode is supported
        self.chars: list[str] = []
        self.fan_chars: list[str] = []

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
        self.set_primary_service(serv_thermostat)

        # Current mode characteristics
        self.char_current_heat_cool = serv_thermostat.configure_char(
            CHAR_CURRENT_HEATING_COOLING, value=0
        )

        self._configure_hvac_modes(state)
        # Must set the value first as setting
        # valid_values happens before setting
        # the value and if 0 is not a valid
        # value this will throw
        self.char_target_heat_cool = serv_thermostat.configure_char(
            CHAR_TARGET_HEATING_COOLING, value=list(self.hc_homekit_to_hass)[0]
        )
        self.char_target_heat_cool.override_properties(
            valid_values=self.hc_hass_to_homekit
        )
        self.char_target_heat_cool.allow_invalid_client_values = True
        # Current and target temperature characteristics

        self.char_current_temp = serv_thermostat.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=21.0
        )

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

        fan_modes: dict[str, str] = {}
        self.ordered_fan_speeds: list[str] = []

        if features & ClimateEntityFeature.FAN_MODE:
            fan_modes = {
                fan_mode.lower(): fan_mode
                for fan_mode in attributes.get(ATTR_FAN_MODES) or []
            }
            if fan_modes and PRE_DEFINED_FAN_MODES.intersection(fan_modes):
                self.ordered_fan_speeds = [
                    speed for speed in ORDERED_FAN_SPEEDS if speed in fan_modes
                ]
                self.fan_chars.append(CHAR_ROTATION_SPEED)

        if FAN_AUTO in fan_modes and (FAN_ON in fan_modes or self.ordered_fan_speeds):
            self.fan_chars.append(CHAR_TARGET_FAN_STATE)

        self.fan_modes = fan_modes
        if (
            features & ClimateEntityFeature.SWING_MODE
            and (swing_modes := attributes.get(ATTR_SWING_MODES))
            and PRE_DEFINED_SWING_MODES.intersection(swing_modes)
        ):
            self.swing_on_mode = next(
                iter(
                    swing_mode
                    for swing_mode in SWING_MODE_PREFERRED_ORDER
                    if swing_mode in swing_modes
                )
            )
            self.fan_chars.append(CHAR_SWING_MODE)

        if self.fan_chars:
            if attributes.get(ATTR_HVAC_ACTION) is not None:
                self.fan_chars.append(CHAR_CURRENT_FAN_STATE)
            serv_fan = self.add_preload_service(SERV_FANV2, self.fan_chars)
            serv_thermostat.add_linked_service(serv_fan)
            self.char_active = serv_fan.configure_char(
                CHAR_ACTIVE, value=1, setter_callback=self._set_fan_active
            )
            if CHAR_SWING_MODE in self.fan_chars:
                self.char_swing = serv_fan.configure_char(
                    CHAR_SWING_MODE,
                    value=0,
                    setter_callback=self._set_fan_swing_mode,
                )
                self.char_swing.display_name = "Swing Mode"
            if CHAR_ROTATION_SPEED in self.fan_chars:
                self.char_speed = serv_fan.configure_char(
                    CHAR_ROTATION_SPEED,
                    value=100,
                    properties={PROP_MIN_STEP: 100 / len(self.ordered_fan_speeds)},
                    setter_callback=self._set_fan_speed,
                )
                self.char_speed.display_name = "Fan Mode"
            if CHAR_CURRENT_FAN_STATE in self.fan_chars:
                self.char_current_fan_state = serv_fan.configure_char(
                    CHAR_CURRENT_FAN_STATE,
                    value=0,
                )
                self.char_current_fan_state.display_name = "Fan State"
            if CHAR_TARGET_FAN_STATE in self.fan_chars and FAN_AUTO in self.fan_modes:
                self.char_target_fan_state = serv_fan.configure_char(
                    CHAR_TARGET_FAN_STATE,
                    value=0,
                    setter_callback=self._set_fan_auto,
                )
                self.char_target_fan_state.display_name = "Fan Auto"

        self.async_update_state(state)

        serv_thermostat.setter_callback = self._set_chars

    def _set_fan_swing_mode(self, swing_on: int) -> None:
        _LOGGER.debug("%s: Set swing mode to %s", self.entity_id, swing_on)
        mode = self.swing_on_mode if swing_on else SWING_OFF
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_SWING_MODE: mode}
        self.async_call_service(DOMAIN_CLIMATE, SERVICE_SET_SWING_MODE, params)

    def _set_fan_speed(self, speed: int) -> None:
        _LOGGER.debug("%s: Set fan speed to %s", self.entity_id, speed)
        mode = percentage_to_ordered_list_item(self.ordered_fan_speeds, speed - 1)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: mode}
        self.async_call_service(DOMAIN_CLIMATE, SERVICE_SET_FAN_MODE, params)

    def _get_on_mode(self) -> str:
        if self.ordered_fan_speeds:
            return percentage_to_ordered_list_item(self.ordered_fan_speeds, 50)
        return self.fan_modes[FAN_ON]

    def _set_fan_active(self, active: int) -> None:
        _LOGGER.debug("%s: Set fan active to %s", self.entity_id, active)
        if FAN_OFF not in self.fan_modes:
            _LOGGER.debug(
                "%s: Fan does not support off, resetting to on", self.entity_id
            )
            self.char_active.value = 1
            self.char_active.notify()
            return
        mode = self._get_on_mode() if active else self.fan_modes[FAN_OFF]
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: mode}
        self.async_call_service(DOMAIN_CLIMATE, SERVICE_SET_FAN_MODE, params)

    def _set_fan_auto(self, auto: int) -> None:
        _LOGGER.debug("%s: Set fan auto to %s", self.entity_id, auto)
        mode = self.fan_modes[FAN_AUTO] if auto else self._get_on_mode()
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: mode}
        self.async_call_service(DOMAIN_CLIMATE, SERVICE_SET_FAN_MODE, params)

    def _temperature_to_homekit(self, temp: float) -> float:
        return temperature_to_homekit(temp, self._unit)

    def _temperature_to_states(self, temp: float) -> float:
        return temperature_to_states(temp, self._unit)

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
                hc_current_temp = _get_current_temperature(state, self._unit)
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
            # `SERVICE_SET_TEMPERATURE_THERMOSTAT` service so we made a call to
            # `SERVICE_SET_HVAC_MODE_THERMOSTAT` before calling `SERVICE_SET_TEMPERATURE_THERMOSTAT`
            # to ensure the device is in the right mode before setting the temp.
            self.async_call_service(
                DOMAIN_CLIMATE,
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
            high = self.char_cooling_thresh_temp.value
            low = self.char_heating_thresh_temp.value
            min_temp, max_temp = self.get_temperature_range(state)
            if CHAR_COOLING_THRESHOLD_TEMPERATURE in char_values:
                events.append(
                    f"{CHAR_COOLING_THRESHOLD_TEMPERATURE} to"
                    f" {char_values[CHAR_COOLING_THRESHOLD_TEMPERATURE]}°C"
                )
                high = char_values[CHAR_COOLING_THRESHOLD_TEMPERATURE]
                # If the device doesn't support TARGET_TEMPATURE
                # this can happen
                if high < low:
                    low = high - HEAT_COOL_DEADBAND
            if CHAR_HEATING_THRESHOLD_TEMPERATURE in char_values:
                events.append(
                    f"{CHAR_HEATING_THRESHOLD_TEMPERATURE} to"
                    f" {char_values[CHAR_HEATING_THRESHOLD_TEMPERATURE]}°C"
                )
                low = char_values[CHAR_HEATING_THRESHOLD_TEMPERATURE]
                # If the device doesn't support TARGET_TEMPATURE
                # this can happen
                if low > high:
                    high = low + HEAT_COOL_DEADBAND

            high = min(high, max_temp)
            low = max(low, min_temp)

            params.update(
                {
                    ATTR_TARGET_TEMP_HIGH: self._temperature_to_states(high),
                    ATTR_TARGET_TEMP_LOW: self._temperature_to_states(low),
                }
            )

        if service:
            self.async_call_service(
                DOMAIN_CLIMATE,
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

    def get_temperature_range(self, state: State) -> tuple[float, float]:
        """Return min and max temperature range."""
        return _get_temperature_range_from_state(
            state,
            self._unit,
            DEFAULT_MIN_TEMP,
            DEFAULT_MAX_TEMP,
        )

    def set_target_humidity(self, value: float) -> None:
        """Set target humidity to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set target humidity to %d", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_HUMIDITY: value}
        self.async_call_service(
            DOMAIN_CLIMATE, SERVICE_SET_HUMIDITY, params, f"{value}{PERCENTAGE}"
        )

    @callback
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

        # Update current temperature
        current_temp = _get_current_temperature(new_state, self._unit)
        if current_temp is not None:
            self.char_current_temp.set_value(current_temp)

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

        # Update cooling threshold temperature if characteristic exists
        if self.char_cooling_thresh_temp:
            cooling_thresh = attributes.get(ATTR_TARGET_TEMP_HIGH)
            if isinstance(cooling_thresh, (int, float)):
                cooling_thresh = self._temperature_to_homekit(cooling_thresh)
                self.char_cooling_thresh_temp.set_value(cooling_thresh)

        # Update heating threshold temperature if characteristic exists
        if self.char_heating_thresh_temp:
            heating_thresh = attributes.get(ATTR_TARGET_TEMP_LOW)
            if isinstance(heating_thresh, (int, float)):
                heating_thresh = self._temperature_to_homekit(heating_thresh)
                self.char_heating_thresh_temp.set_value(heating_thresh)

        # Update target temperature
        target_temp = _get_target_temperature(new_state, self._unit)
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
            self._async_update_fan_state(new_state)

    @callback
    def _async_update_fan_state(self, new_state: State) -> None:
        """Update state without rechecking the device features."""
        attributes = new_state.attributes

        if CHAR_SWING_MODE in self.fan_chars and (
            swing_mode := attributes.get(ATTR_SWING_MODE)
        ):
            swing = 1 if swing_mode in PRE_DEFINED_SWING_MODES else 0
            self.char_swing.set_value(swing)

        fan_mode = attributes.get(ATTR_FAN_MODE)
        fan_mode_lower = fan_mode.lower() if isinstance(fan_mode, str) else None
        if (
            CHAR_ROTATION_SPEED in self.fan_chars
            and fan_mode_lower in self.ordered_fan_speeds
        ):
            self.char_speed.set_value(
                ordered_list_item_to_percentage(self.ordered_fan_speeds, fan_mode_lower)
            )

        if CHAR_TARGET_FAN_STATE in self.fan_chars:
            self.char_target_fan_state.set_value(1 if fan_mode_lower == FAN_AUTO else 0)

        if CHAR_CURRENT_FAN_STATE in self.fan_chars and (
            hvac_action := attributes.get(ATTR_HVAC_ACTION)
        ):
            self.char_current_fan_state.set_value(
                HC_HASS_TO_HOMEKIT_FAN_STATE[hvac_action]
            )

        self.char_active.set_value(
            int(new_state.state != HVACMode.OFF and fan_mode_lower != FAN_OFF)
        )


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
            )
        )
        self._unit = self.hass.config.units.temperature_unit
        state = self.hass.states.get(self.entity_id)
        assert state
        min_temp, max_temp = self.get_temperature_range(state)

        serv_thermostat = self.add_preload_service(SERV_THERMOSTAT)

        self.char_current_heat_cool = serv_thermostat.configure_char(
            CHAR_CURRENT_HEATING_COOLING, value=1
        )
        self.char_target_heat_cool = serv_thermostat.configure_char(
            CHAR_TARGET_HEATING_COOLING,
            value=1,
            setter_callback=self.set_heat_cool,
            valid_values=HC_HOMEKIT_VALID_MODES_WATER_HEATER,
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
        return _get_temperature_range_from_state(
            state,
            self._unit,
            DEFAULT_MIN_TEMP_WATER_HEATER,
            DEFAULT_MAX_TEMP_WATER_HEATER,
        )

    def set_heat_cool(self, value: int) -> None:
        """Change operation mode to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set heat-cool to %d", self.entity_id, value)
        if HC_HOMEKIT_TO_HASS[value] != HVACMode.HEAT:
            self.char_target_heat_cool.set_value(1)  # Heat

    def set_target_temperature(self, value: float) -> None:
        """Set target temperature to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set target temperature to %.1f°C", self.entity_id, value)
        temperature = temperature_to_states(value, self._unit)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_TEMPERATURE: temperature}
        self.async_call_service(
            DOMAIN_WATER_HEATER,
            SERVICE_SET_TEMPERATURE_WATER_HEATER,
            params,
            f"{temperature}{self._unit}",
        )

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update water_heater state after state change."""
        # Update current and target temperature
        target_temperature = _get_target_temperature(new_state, self._unit)
        if target_temperature is not None:
            self.char_target_temp.set_value(target_temperature)

        current_temperature = _get_current_temperature(new_state, self._unit)
        if current_temperature is not None:
            self.char_current_temp.set_value(current_temperature)

        # Update display units
        if self._unit and self._unit in UNIT_HASS_TO_HOMEKIT:
            unit = UNIT_HASS_TO_HOMEKIT[self._unit]
            self.char_display_units.set_value(unit)

        # Update target operation mode
        if new_state.state:
            self.char_target_heat_cool.set_value(1)  # Heat


def _get_temperature_range_from_state(
    state: State, unit: str, default_min: float, default_max: float
) -> tuple[float, float]:
    """Calculate the temperature range from a state."""
    if min_temp := state.attributes.get(ATTR_MIN_TEMP):
        min_temp = round(temperature_to_homekit(min_temp, unit) * 2) / 2
    else:
        min_temp = default_min

    if max_temp := state.attributes.get(ATTR_MAX_TEMP):
        max_temp = round(temperature_to_homekit(max_temp, unit) * 2) / 2
    else:
        max_temp = default_max

    # Handle reversed temperature range
    min_temp, max_temp = get_min_max(min_temp, max_temp)

    # Homekit only supports 10-38, overwriting
    # the max to appears to work, but less than 0 causes
    # a crash on the home app
    min_temp = max(min_temp, 0)
    max_temp = max(max_temp, min_temp)

    return min_temp, max_temp


def _get_target_temperature(state: State, unit: str) -> float | None:
    """Calculate the target temperature from a state."""
    target_temp = state.attributes.get(ATTR_TEMPERATURE)
    if isinstance(target_temp, (int, float)):
        return temperature_to_homekit(target_temp, unit)
    return None


def _get_current_temperature(state: State, unit: str) -> float | None:
    """Calculate the current temperature from a state."""
    target_temp = state.attributes.get(ATTR_CURRENT_TEMPERATURE)
    if isinstance(target_temp, (int, float)):
        return temperature_to_homekit(target_temp, unit)
    return None
