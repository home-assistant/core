"""Class to hold all light accessories."""
import logging

from pyhap.const import CATEGORY_FAN

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_SPEED,
    ATTR_SPEED_LIST,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_SPEED,
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_ROTATION_DIRECTION,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    SERV_FANV2,
)
from .util import HomeKitSpeedMapping

_LOGGER = logging.getLogger(__name__)


@TYPES.register("Fan")
class Fan(HomeAccessory):
    """Generate a Fan accessory for a fan entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args):
        """Initialize a new Fan accessory object."""
        super().__init__(*args, category=CATEGORY_FAN)
        chars = []
        state = self.hass.states.get(self.entity_id)

        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if features & SUPPORT_DIRECTION:
            chars.append(CHAR_ROTATION_DIRECTION)
        if features & SUPPORT_OSCILLATE:
            chars.append(CHAR_SWING_MODE)
        if features & SUPPORT_SET_SPEED:
            speed_list = self.hass.states.get(self.entity_id).attributes.get(
                ATTR_SPEED_LIST
            )
            self.speed_mapping = HomeKitSpeedMapping(speed_list)
            chars.append(CHAR_ROTATION_SPEED)

        serv_fan = self.add_preload_service(SERV_FANV2, chars)
        self.char_active = serv_fan.configure_char(CHAR_ACTIVE, value=0)

        self.char_direction = None
        self.char_speed = None
        self.char_swing = None

        if CHAR_ROTATION_DIRECTION in chars:
            self.char_direction = serv_fan.configure_char(
                CHAR_ROTATION_DIRECTION, value=0
            )

        if CHAR_ROTATION_SPEED in chars:
            # Initial value is set to 100 because 0 is a special value (off). 100 is
            # an arbitrary non-zero value. It is updated immediately by async_update_state
            # to set to the correct initial value.
            self.char_speed = serv_fan.configure_char(CHAR_ROTATION_SPEED, value=100)

        if CHAR_SWING_MODE in chars:
            self.char_swing = serv_fan.configure_char(CHAR_SWING_MODE, value=0)
        self.async_update_state(state)
        serv_fan.setter_callback = self._set_chars

    def _set_chars(self, char_values):
        _LOGGER.debug("Fan _set_chars: %s", char_values)
        if CHAR_ACTIVE in char_values:
            if char_values[CHAR_ACTIVE]:
                # If the device supports set speed we
                # do not want to turn on as it will take
                # the fan to 100% than to the desired speed.
                #
                # Setting the speed will take care of turning
                # on the fan if SUPPORT_SET_SPEED is set.
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
            self.set_speed(char_values[CHAR_ROTATION_SPEED])

    def set_state(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set state to %d", self.entity_id, value)
        service = SERVICE_TURN_ON if value == 1 else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_direction(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set direction to %d", self.entity_id, value)
        direction = DIRECTION_REVERSE if value == 1 else DIRECTION_FORWARD
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_DIRECTION: direction}
        self.call_service(DOMAIN, SERVICE_SET_DIRECTION, params, direction)

    def set_oscillating(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set oscillating to %d", self.entity_id, value)
        oscillating = value == 1
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_OSCILLATING: oscillating}
        self.call_service(DOMAIN, SERVICE_OSCILLATE, params, oscillating)

    def set_speed(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug("%s: Set speed to %d", self.entity_id, value)
        speed = self.speed_mapping.speed_to_states(value)
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_SPEED: speed}
        self.call_service(DOMAIN, SERVICE_SET_SPEED, params, speed)

    @callback
    def async_update_state(self, new_state):
        """Update fan after state change."""
        # Handle State
        state = new_state.state
        if state in (STATE_ON, STATE_OFF):
            self._state = 1 if state == STATE_ON else 0
            if self.char_active.value != self._state:
                self.char_active.set_value(self._state)

        # Handle Direction
        if self.char_direction is not None:
            direction = new_state.attributes.get(ATTR_DIRECTION)
            if direction in (DIRECTION_FORWARD, DIRECTION_REVERSE):
                hk_direction = 1 if direction == DIRECTION_REVERSE else 0
                if self.char_direction.value != hk_direction:
                    self.char_direction.set_value(hk_direction)

        # Handle Speed
        if self.char_speed is not None and state != STATE_OFF:
            # We do not change the homekit speed when turning off
            # as it will clear the restore state
            speed = new_state.attributes.get(ATTR_SPEED)
            hk_speed_value = self.speed_mapping.speed_to_homekit(speed)
            if hk_speed_value is not None and self.char_speed.value != hk_speed_value:
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
                if hk_speed_value == 0 and state == STATE_ON:
                    hk_speed_value = 1
                if self.char_speed.value != hk_speed_value:
                    self.char_speed.set_value(hk_speed_value)

        # Handle Oscillating
        if self.char_swing is not None:
            oscillating = new_state.attributes.get(ATTR_OSCILLATING)
            if isinstance(oscillating, bool):
                hk_oscillating = 1 if oscillating else 0
                if self.char_swing.value != hk_oscillating:
                    self.char_swing.set_value(hk_oscillating)
