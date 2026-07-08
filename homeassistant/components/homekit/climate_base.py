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
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_SWING_MODE,
    SWING_OFF,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import State

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
from .const import CHAR_CURRENT_TEMPERATURE, PROP_MAX_VALUE, PROP_MIN_VALUE
from .util import temperature_to_homekit, temperature_to_states

_LOGGER = logging.getLogger(__name__)


class HomeKitClimateAccessory(HomeAccessory):
    """Base class for the Thermostat and HeaterCooler accessories."""

    # Configured by subclasses only when the entity exposes the mode.
    char_speed: Characteristic
    char_swing: Characteristic

    char_current_temp: Characteristic

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
