"""Class to hold all light accessories."""
import logging

from pyhap.const import CATEGORY_FAN

from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, ATTR_SPEED,
    DIRECTION_FORWARD, DIRECTION_REVERSE, DOMAIN, SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION, SUPPORT_DIRECTION, SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_OFF, STATE_ON,
    SERVICE_TURN_OFF, SERVICE_TURN_ON)

from . import TYPES
from .accessories import HomeAccessory, debounce
from .const import (
    CHAR_ACTIVE, CHAR_ROTATION_DIRECTION, CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE, SERV_FANV2, PROP_STEP)
from .util import fan_speed_to_value, fan_value_to_speed

_LOGGER = logging.getLogger(__name__)


@TYPES.register('Fan')
class Fan(HomeAccessory):
    """Generate a Fan accessory for a fan entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args):
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_FAN)
        self._flag = {CHAR_ACTIVE: False,
                      CHAR_ROTATION_SPEED: False,
                      CHAR_ROTATION_DIRECTION: False,
                      CHAR_SWING_MODE: False}
        self._state = 0

        self.chars = []
        features = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        if features & SUPPORT_SET_SPEED:
            self.chars.append(CHAR_ROTATION_SPEED)
        if features & SUPPORT_DIRECTION:
            self.chars.append(CHAR_ROTATION_DIRECTION)
        if features & SUPPORT_OSCILLATE:
            self.chars.append(CHAR_SWING_MODE)

        serv_fan = self.add_preload_service(SERV_FANV2, self.chars)
        self.char_active = serv_fan.configure_char(
            CHAR_ACTIVE, value=0, setter_callback=self.set_state)

        if CHAR_ROTATION_SPEED in self.chars:
            self.char_speed = serv_fan.configure_char(
                CHAR_ROTATION_SPEED, value=0,
                properties={PROP_STEP: 33.33},
                setter_callback=self.set_speed)

        if CHAR_ROTATION_DIRECTION in self.chars:
            self.char_direction = serv_fan.configure_char(
                CHAR_ROTATION_DIRECTION, value=0,
                setter_callback=self.set_direction)

        if CHAR_SWING_MODE in self.chars:
            self.char_swing = serv_fan.configure_char(
                CHAR_SWING_MODE, value=0, setter_callback=self.set_oscillating)

    def set_state(self, value):
        """Set state if call came from HomeKit."""
        if self._state == value:
            return

        _LOGGER.debug('%s: Set state to %d', self.entity_id, value)
        self._flag[CHAR_ACTIVE] = True
        service = SERVICE_TURN_ON if value == 1 else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    @debounce
    def set_speed(self, value):
        """Set speed if call came from HomeKit."""
        _LOGGER.debug('%s: Set speed to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_SPEED] = True
        if value != 0:
            params = {ATTR_ENTITY_ID: self.entity_id,
                      ATTR_SPEED: fan_value_to_speed(value)}
            self.hass.services.call(DOMAIN, SERVICE_TURN_ON, params)
        else:
            params = {ATTR_ENTITY_ID: self.entity_id}
            self.hass.services.call(DOMAIN, SERVICE_TURN_OFF, params)

    def set_direction(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set direction to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_DIRECTION] = True
        direction = DIRECTION_REVERSE if value == 1 else DIRECTION_FORWARD
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_DIRECTION: direction}
        self.hass.services.call(DOMAIN, SERVICE_SET_DIRECTION, params)

    def set_oscillating(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set oscillating to %d', self.entity_id, value)
        self._flag[CHAR_SWING_MODE] = True
        oscillating = True if value == 1 else False
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_OSCILLATING: oscillating}
        self.hass.services.call(DOMAIN, SERVICE_OSCILLATE, params)

    def update_state(self, new_state):
        """Update fan after state change."""
        # Handle State
        state = new_state.state
        if state in (STATE_ON, STATE_OFF):
            self._state = 1 if state == STATE_ON else 0
            if not self._flag[CHAR_ACTIVE] and \
                    self.char_active.value != self._state:
                self.char_active.set_value(self._state)
            self._flag[CHAR_ACTIVE] = False

        # Handle Speed
        if CHAR_ROTATION_SPEED in self.chars:
            speed = new_state.attributes.get(ATTR_SPEED)
            hk_speed = fan_speed_to_value(speed)
            if not self._flag[CHAR_ROTATION_SPEED] and \
                    isinstance(hk_speed, int):
                if self.char_speed.value != hk_speed:
                    self.char_speed.set_value(hk_speed)
            self._flag[CHAR_ROTATION_SPEED] = False

        # Handle Direction
        if CHAR_ROTATION_DIRECTION in self.chars:
            direction = new_state.attributes.get(ATTR_DIRECTION)
            if not self._flag[CHAR_ROTATION_DIRECTION] and \
                    direction in (DIRECTION_FORWARD, DIRECTION_REVERSE):
                hk_direction = 1 if direction == DIRECTION_REVERSE else 0
                if self.char_direction.value != hk_direction:
                    self.char_direction.set_value(hk_direction)
            self._flag[CHAR_ROTATION_DIRECTION] = False

        # Handle Oscillating
        if CHAR_SWING_MODE in self.chars:
            oscillating = new_state.attributes.get(ATTR_OSCILLATING)
            if not self._flag[CHAR_SWING_MODE] and \
                    oscillating in (True, False):
                hk_oscillating = 1 if oscillating else 0
                if self.char_swing.value != hk_oscillating:
                    self.char_swing.set_value(hk_oscillating)
            self._flag[CHAR_SWING_MODE] = False
