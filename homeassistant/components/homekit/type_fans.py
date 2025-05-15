"""Class to hold all fan accessories."""

import logging
from typing import Any

from pyhap.const import CATEGORY_FAN
from pyhap.service import Service

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import State, callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_CONFIGURED_NAME,
    CHAR_NAME,
    CHAR_ON,
    CHAR_ROTATION_DIRECTION,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_FAN_STATE,
    PROP_MIN_STEP,
    SERV_FANV2,
    SERV_SWITCH,
)
from .util import cleanup_name_for_homekit

_LOGGER = logging.getLogger(__name__)


@TYPES.register("Fan")
class Fan(HomeAccessory):
    """Generate a Fan accessory for a fan entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args: Any, category: int = CATEGORY_FAN) -> None:
        """Initialize a new Fan accessory object."""
        super().__init__(*args, category=category)
        self.chars: list[str] = []
        state = self.hass.states.get(self.entity_id)
        assert state
        self._reload_on_change_attrs.extend(
            (
                ATTR_PERCENTAGE_STEP,
                ATTR_PRESET_MODES,
            )
        )

        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        percentage_step = state.attributes.get(ATTR_PERCENTAGE_STEP, 1)
        self.preset_modes: list[str] | None = state.attributes.get(ATTR_PRESET_MODES)

        if features & FanEntityFeature.DIRECTION:
            self.chars.append(CHAR_ROTATION_DIRECTION)
        if features & FanEntityFeature.OSCILLATE:
            self.chars.append(CHAR_SWING_MODE)
        if features & FanEntityFeature.SET_SPEED:
            self.chars.append(CHAR_ROTATION_SPEED)

        serv_fan = self.create_services()

        self.char_direction = None
        self.char_speed = None
        self.char_swing = None
        self.char_target_fan_state = None
        self.preset_mode_chars = {}

        if CHAR_ROTATION_DIRECTION in self.chars:
            self.char_direction = serv_fan.configure_char(
                CHAR_ROTATION_DIRECTION, value=0
            )

        if CHAR_ROTATION_SPEED in self.chars:
            # Initial value is set to 100 because 0 is a special value (off). 100 is
            # an arbitrary non-zero value. It is updated immediately by async_update_state
            # to set to the correct initial value.
            self.char_speed = serv_fan.configure_char(
                CHAR_ROTATION_SPEED,
                value=100,
                properties={PROP_MIN_STEP: percentage_step},
            )

        if (
            self.preset_modes
            and len(self.preset_modes) == 1
            # NOTE: This would be missing for air purifiers
            and CHAR_TARGET_FAN_STATE in self.chars
        ):
            self.char_target_fan_state = serv_fan.configure_char(
                CHAR_TARGET_FAN_STATE,
                value=0,
            )
        elif self.preset_modes:
            for preset_mode in self.preset_modes:
                if not self.should_add_preset_mode_switch(preset_mode):
                    continue

                preset_serv = self.add_preload_service(
                    SERV_SWITCH,
                    [CHAR_NAME, CHAR_CONFIGURED_NAME],
                    unique_id=preset_mode,
                )
                serv_fan.add_linked_service(preset_serv)
                preset_serv.configure_char(
                    CHAR_NAME,
                    value=cleanup_name_for_homekit(
                        f"{self.display_name} {preset_mode}"
                    ),
                )
                preset_serv.configure_char(
                    CHAR_CONFIGURED_NAME, value=cleanup_name_for_homekit(preset_mode)
                )

                def setter_callback(value: int, preset_mode: str = preset_mode) -> None:
                    self.set_preset_mode(value, preset_mode)

                self.preset_mode_chars[preset_mode] = preset_serv.configure_char(
                    CHAR_ON,
                    value=False,
                    setter_callback=setter_callback,
                )

        if CHAR_SWING_MODE in self.chars:
            self.char_swing = serv_fan.configure_char(CHAR_SWING_MODE, value=0)
        self.async_update_state(state)
        serv_fan.setter_callback = self.set_chars

    def create_services(self) -> Service:
        """Create and configure the primary service for this accessory."""
        if self.preset_modes and len(self.preset_modes) == 1:
            self.chars.append(CHAR_TARGET_FAN_STATE)
        serv_fan = self.add_preload_service(SERV_FANV2, self.chars)
        self.set_primary_service(serv_fan)
        self.char_active = serv_fan.configure_char(CHAR_ACTIVE, value=0)
        return serv_fan

    def should_add_preset_mode_switch(self, preset_mode: str) -> bool:
        """Check if a preset mode switch should be added.

        Always true for fans, but can be overridden by subclasses.
        """
        return True

    def set_chars(self, char_values: dict[str, Any]) -> None:
        """Set characteristic values."""
        _LOGGER.debug("Fan set_chars: %s", char_values)
        if CHAR_ACTIVE in char_values:
            if char_values[CHAR_ACTIVE]:
                # If the device supports set speed we
                # do not want to turn on as it will take
                # the fan to 100% than to the desired speed.
                #
                # Setting the speed will take care of turning
                # on the fan if FanEntityFeature.SET_SPEED is set.
                if not self.char_speed or CHAR_ROTATION_SPEED not in char_values:
                    self.set_state(1)
            else:
                # Its off, nothing more to do as setting the
                # other chars will likely turn it back on which
                # is what we want to avoid
                self.set_state(0)
                return

        if CHAR_SWING_MODE in char_values:
            self.set_oscillating(char_values[CHAR_SWING_MODE])
        if CHAR_ROTATION_DIRECTION in char_values:
            self.set_direction(char_values[CHAR_ROTATION_DIRECTION])

        # We always do this LAST to ensure they
        # get the speed they asked for
        if CHAR_ROTATION_SPEED in char_values:
            self.set_percentage(char_values[CHAR_ROTATION_SPEED])
        if CHAR_TARGET_FAN_STATE in char_values:
            self.set_single_preset_mode(char_values[CHAR_TARGET_FAN_STATE])

    def set_single_preset_mode(self, value: int) -> None:
        """Set auto call came from HomeKit."""
        params: dict[str, Any] = {ATTR_ENTITY_ID: self.entity_id}
        if value:
            assert self.preset_modes
            _LOGGER.debug(
                "%s: Set auto to 1 (%s)", self.entity_id, self.preset_modes[0]
            )
            params[ATTR_PRESET_MODE] = self.preset_modes[0]
            self.async_call_service(FAN_DOMAIN, SERVICE_SET_PRESET_MODE, params)
        elif current_state := self.hass.states.get(self.entity_id):
            percentage: float = current_state.attributes.get(ATTR_PERCENTAGE) or 50.0
            params[ATTR_PERCENTAGE] = percentage
            _LOGGER.debug("%s: Set auto to 0", self.entity_id)
            self.async_call_service(FAN_DOMAIN, SERVICE_TURN_ON, params)

    def set_preset_mode(self, value: int, preset_mode: str) -> None:
        """Set preset_mode if call came from HomeKit."""
        _LOGGER.debug(
            "%s: Set preset_mode %s to %d", self.entity_id, preset_mode, value
        )
        params = {ATTR_ENTITY_ID: self.entity_id}
        if value:
            params[ATTR_PRESET_MODE] = preset_mode
            self.async_call_service(FAN_DOMAIN, SERVICE_SET_PRESET_MODE, params)
        else:
            self.async_call_service(FAN_DOMAIN, SERVICE_TURN_ON, params)

    def set_state(self, value: int) -> None:
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set state to %d", self.entity_id, value)
        service = SERVICE_TURN_ON if value == 1 else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.async_call_service(FAN_DOMAIN, service, params)

    def set_direction(self, value: int) -> None:
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set direction to %d", self.entity_id, value)
        direction = DIRECTION_REVERSE if value == 1 else DIRECTION_FORWARD
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_DIRECTION: direction}
        self.async_call_service(FAN_DOMAIN, SERVICE_SET_DIRECTION, params, direction)

    def set_oscillating(self, value: int) -> None:
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set oscillating to %d", self.entity_id, value)
        oscillating = value == 1
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_OSCILLATING: oscillating}
        self.async_call_service(FAN_DOMAIN, SERVICE_OSCILLATE, params, oscillating)

    def set_percentage(self, value: float) -> None:
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set speed to %d", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_PERCENTAGE: value}
        self.async_call_service(FAN_DOMAIN, SERVICE_SET_PERCENTAGE, params, value)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update fan after state change."""
        # Handle State
        state = new_state.state
        attributes = new_state.attributes
        if state in (STATE_ON, STATE_OFF):
            self._state = 1 if state == STATE_ON else 0
            self.char_active.set_value(self._state)

        # Handle Direction
        if self.char_direction is not None:
            direction = new_state.attributes.get(ATTR_DIRECTION)
            if direction in (DIRECTION_FORWARD, DIRECTION_REVERSE):
                hk_direction = 1 if direction == DIRECTION_REVERSE else 0
                self.char_direction.set_value(hk_direction)

        # Handle Speed
        if self.char_speed is not None and state != STATE_OFF:
            # We do not change the homekit speed when turning off
            # as it will clear the restore state
            percentage = attributes.get(ATTR_PERCENTAGE)
            # If the homeassistant component reports its speed as the first entry
            # in its speed list but is not off, the hk_speed_value is 0. But 0
            # is a special value in homekit. When you turn on a homekit accessory
            # it will try to restore the last rotation speed state which will be
            # the last value saved by char_speed.set_value. But if it is set to
            # 0, HomeKit will update the rotation speed to 100 as it thinks 0 is
            # off.
            #
            # Therefore, if the hk_speed_value is 0 and the device is still on,
            # the rotation speed is mapped to 1 otherwise the update is ignored
            # in order to avoid this incorrect behavior.
            if percentage == 0 and state == STATE_ON:
                percentage = max(1, self.char_speed.properties[PROP_MIN_STEP])
            if percentage is not None:
                self.char_speed.set_value(percentage)

        # Handle Oscillating
        if self.char_swing is not None:
            oscillating = attributes.get(ATTR_OSCILLATING)
            if isinstance(oscillating, bool):
                hk_oscillating = 1 if oscillating else 0
                self.char_swing.set_value(hk_oscillating)

        current_preset_mode = attributes.get(ATTR_PRESET_MODE)
        if self.char_target_fan_state is not None:
            # Handle single preset mode
            self.char_target_fan_state.set_value(int(current_preset_mode is not None))
            return

        # Handle multiple preset modes
        for preset_mode, char in self.preset_mode_chars.items():
            hk_value = 1 if preset_mode == current_preset_mode else 0
            char.set_value(hk_value)
