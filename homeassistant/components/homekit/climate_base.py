"""Base class shared by the climate accessory types."""

from collections.abc import Mapping
import logging
from typing import Any

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_THERMOSTAT
from pyhap.service import Service

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_OFF,
    FAN_ON,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_SWING_MODE,
    SWING_OFF,
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
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .accessories import HomeAccessory
from .climate_util import (
    fan_mode_to_speed,
    fan_speed_to_mode,
    get_fan_modes_and_speeds,
    get_swing_off_mode,
    get_swing_on_mode,
    get_temperature_range_from_state,
    is_swing_on,
    resolve_target_temp_range,
    temperature_attribute_to_homekit,
)
from .const import (
    CHAR_ACTIVE,
    CHAR_CURRENT_FAN_STATE,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_FAN_STATE,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
    SERV_FANV2,
)
from .util import temperature_to_homekit, temperature_to_states

_LOGGER = logging.getLogger(__name__)

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
    HVACAction.PREHEATING: FAN_STATE_IDLE,
    HVACAction.DEFROSTING: FAN_STATE_IDLE,
}


class HomeKitClimateAccessory(HomeAccessory):
    """Base class for the Thermostat and HeaterCooler accessories."""

    # Configured by subclasses only when the entity exposes the mode.
    char_speed: Characteristic
    char_swing: Characteristic

    char_current_temp: Characteristic

    # Configured by _configure_fan_service when fan_chars is non-empty.
    char_fan_active: Characteristic
    char_target_fan_state: Characteristic
    char_current_fan_state: Characteristic

    def __init__(self, *args: Any) -> None:
        """Initialize the shared climate accessory state."""
        super().__init__(*args, category=CATEGORY_THERMOSTAT)
        self._unit = self.hass.config.units.temperature_unit

        state = self.hass.states.get(self.entity_id)
        assert state
        attributes = state.attributes
        features = attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        # ``fan_modes`` maps lowercased names to their original casing;
        # ``ordered_fan_speeds`` holds the predefined speeds in HomeKit order.
        self.fan_modes: dict[str, str] = {}
        self.ordered_fan_speeds: list[str] = []
        if features & ClimateEntityFeature.FAN_MODE:
            self.fan_modes, self.ordered_fan_speeds = get_fan_modes_and_speeds(
                attributes
            )

        self.swing_on_mode: str | None = None
        self.swing_off_mode: str = SWING_OFF
        if features & ClimateEntityFeature.SWING_MODE:
            self.swing_on_mode = get_swing_on_mode(attributes)
            self.swing_off_mode = get_swing_off_mode(attributes)

        # Characteristics the subclass places on a linked fan service; which
        # ones, if any, is the subclass's policy.
        self.fan_chars: list[str] = []

        # These attributes drive the characteristic set and valid values, so
        # reload the accessory when any of them change.
        self._reload_on_change_attrs.extend(
            (
                ATTR_MIN_TEMP,
                ATTR_MAX_TEMP,
                ATTR_FAN_MODES,
                ATTR_SWING_MODES,
                ATTR_HVAC_MODES,
            )
        )

    def get_temperature_range(self, state: State) -> tuple[float, float]:
        """Return the min and max temperature range."""
        return get_temperature_range_from_state(
            state, self._unit, DEFAULT_MIN_TEMP, DEFAULT_MAX_TEMP
        )

    def _configure_current_temperature_char(self, serv: Service) -> None:
        """Configure the shared current temperature characteristic."""
        self.char_current_temp = serv.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=21.0
        )

    def _configure_target_mode_char(
        self,
        serv: Service,
        char_name: str,
        value: int,
        valid_values: dict[HVACMode, int],
    ) -> Characteristic:
        """Configure a target mode characteristic scoped to the supported modes.

        The value must be set before ``valid_values`` because pyhap applies the
        valid values first and would reject a default outside that set.
        """
        char = serv.configure_char(char_name, value=value)
        char.override_properties(valid_values=valid_values)
        char.allow_invalid_client_values = True
        return char

    def _update_temperature_char(
        self, char: Characteristic, state: State, attr: str
    ) -> None:
        """Set a temperature characteristic from a state attribute, if present."""
        if (
            value := temperature_attribute_to_homekit(state, attr, self._unit)
        ) is not None:
            char.set_value(value)

    def _update_current_temperature_char(self, state: State) -> None:
        """Update the current temperature characteristic from the entity state."""
        self._update_temperature_char(
            self.char_current_temp, state, ATTR_CURRENT_TEMPERATURE
        )

    def _dual_setpoint_params(
        self,
        cool_char: Characteristic,
        heat_char: Characteristic,
        new_high: float | None,
        new_low: float | None,
    ) -> dict[str, float]:
        """Return an ordered high/low target temperature pair for a range write.

        Fills the unchanged side from the current characteristic value and
        enforces the deadband, so the entity always gets a consistent pair.
        """
        high, low = resolve_target_temp_range(
            cool_char.value,
            heat_char.value,
            new_high,
            new_low,
            cool_char.properties[PROP_MIN_VALUE],
            cool_char.properties[PROP_MAX_VALUE],
        )
        return {
            ATTR_TARGET_TEMP_HIGH: self._temperature_to_states(high),
            ATTR_TARGET_TEMP_LOW: self._temperature_to_states(low),
        }

    def _temperature_to_homekit(self, temp: float) -> float:
        """Convert a temperature in the entity's unit to the HomeKit unit."""
        return temperature_to_homekit(temp, self._unit)

    def _temperature_to_states(self, temp: float) -> float:
        """Convert a temperature in the HomeKit unit to the entity's unit."""
        return temperature_to_states(temp, self._unit)

    def _set_fan_speed(self, speed: int) -> None:
        """Send the climate fan mode for a HomeKit rotation speed."""
        _LOGGER.debug("%s: Set fan speed to %s", self.entity_id, speed)
        if not self.ordered_fan_speeds or not 0 < speed <= 100:
            return
        mode = fan_speed_to_mode(self.ordered_fan_speeds, self.fan_modes, speed)
        self.async_call_service(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: mode},
        )

    def _set_swing_mode(self, swing_on: int) -> None:
        """Send the climate swing mode for a HomeKit swing toggle."""
        if self.swing_on_mode is None:
            return
        _LOGGER.debug("%s: Set swing mode to %s", self.entity_id, swing_on)
        mode = self.swing_on_mode if swing_on else self.swing_off_mode
        self.async_call_service(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: self.entity_id, ATTR_SWING_MODE: mode},
        )

    def _update_fan_speed_char(self, attributes: Mapping[str, Any]) -> None:
        """Update the rotation speed characteristic from the current fan mode."""
        # Modes with no predefined speed (e.g. fan auto) keep the last value;
        # HomeKit's slider has no position to represent them.
        if (
            self.ordered_fan_speeds
            and (
                speed := fan_mode_to_speed(
                    self.ordered_fan_speeds, attributes.get(ATTR_FAN_MODE)
                )
            )
            is not None
        ):
            self.char_speed.set_value(speed)

    def _update_swing_char(self, attributes: Mapping[str, Any]) -> None:
        """Update the swing characteristic from the current swing mode."""
        # An absent swing mode keeps the last value; there is nothing to show.
        if self.swing_on_mode is not None and (
            swing_mode := attributes.get(ATTR_SWING_MODE)
        ):
            self.char_swing.set_value(1 if is_swing_on(swing_mode) else 0)

    def _configure_fan_service(self, primary_serv: Service) -> None:
        """Create a linked fan service for the chars in ``fan_chars``."""
        serv_fan = self.add_preload_service(SERV_FANV2, self.fan_chars)
        primary_serv.add_linked_service(serv_fan)
        self.char_fan_active = serv_fan.configure_char(
            CHAR_ACTIVE, value=1, setter_callback=self._set_fan_active
        )
        if CHAR_SWING_MODE in self.fan_chars:
            self.char_swing = serv_fan.configure_char(
                CHAR_SWING_MODE,
                value=0,
                setter_callback=self._set_swing_mode,
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
        if CHAR_TARGET_FAN_STATE in self.fan_chars:
            self.char_target_fan_state = serv_fan.configure_char(
                CHAR_TARGET_FAN_STATE,
                value=0,
                setter_callback=self._set_fan_auto,
            )
            self.char_target_fan_state.display_name = "Fan Auto"

    def _get_on_mode(self) -> str:
        """Return the fan mode to use when leaving auto or turning the fan on."""
        if self.ordered_fan_speeds:
            speed_key = percentage_to_ordered_list_item(self.ordered_fan_speeds, 50)
            return self.fan_modes[speed_key]
        return self.fan_modes[FAN_ON]

    def _set_fan_active(self, active: int) -> None:
        """Send the climate fan mode for a HomeKit fan active toggle."""
        _LOGGER.debug("%s: Set fan active to %s", self.entity_id, active)
        if FAN_OFF not in self.fan_modes:
            _LOGGER.debug(
                "%s: Fan does not support off, resetting to on", self.entity_id
            )
            self.char_fan_active.value = 1
            self.char_fan_active.notify()
            return
        mode = self._get_on_mode() if active else self.fan_modes[FAN_OFF]
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: mode}
        self.async_call_service(CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE, params)

    def _set_fan_auto(self, auto: int) -> None:
        """Send the climate fan mode for a HomeKit fan auto toggle.

        Subclasses must only add CHAR_TARGET_FAN_STATE to ``fan_chars`` when
        FAN_AUTO is in ``fan_modes``; this setter assumes the mode exists.
        """
        _LOGGER.debug("%s: Set fan auto to %s", self.entity_id, auto)
        mode = self.fan_modes[FAN_AUTO] if auto else self._get_on_mode()
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: mode}
        self.async_call_service(CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE, params)

    @callback
    def _async_update_fan_service(self, new_state: State) -> None:
        """Update the linked fan service from the entity state."""
        attributes = new_state.attributes

        self._update_swing_char(attributes)
        self._update_fan_speed_char(attributes)

        fan_mode = attributes.get(ATTR_FAN_MODE)
        fan_mode_lower = fan_mode.lower() if isinstance(fan_mode, str) else None
        if CHAR_TARGET_FAN_STATE in self.fan_chars:
            self.char_target_fan_state.set_value(1 if fan_mode_lower == FAN_AUTO else 0)

        if CHAR_CURRENT_FAN_STATE in self.fan_chars and (
            hvac_action := attributes.get(ATTR_HVAC_ACTION)
        ):
            self.char_current_fan_state.set_value(
                HC_HASS_TO_HOMEKIT_FAN_STATE[hvac_action]
            )

        self.char_fan_active.set_value(
            int(
                new_state.state not in (HVACMode.OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)
                and fan_mode_lower != FAN_OFF
            )
        )
