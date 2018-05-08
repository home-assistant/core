"""Class to hold all light accessories."""
import logging

from pyhap.const import CATEGORY_FAN

from homeassistant.components.fan import (
    ATTR_SPEED, ATTR_SPEED_LIST, SUPPORT_SET_SPEED, SUPPORT_OSCILLATE,
    SUPPORT_DIRECTION, ATTR_OSCILLATING, ATTR_DIRECTION)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, STATE_ON, STATE_OFF, ATTR_ENTITY_ID,
    SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.core import split_entity_id

from . import TYPES
from .accessories import HomeAccessory, debounce
from .const import (
    SERV_FANV2, CHAR_ACTIVE, CHAR_ROTATION_DIRECTION, CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE)

_LOGGER = logging.getLogger(__name__)

ATTR_DIRECTION_LEFT = 'left'
ATTR_DIRECTION_RIGHT = 'right'
ATTR_DIRECTION_CLOCKWISE = 'clockwise'
ATTR_DIRECTION_COUNTER_CLOCKWISE = 'counter_clockwise'

HASS_TO_HOMEKIT = {ATTR_DIRECTION_LEFT: 1,
                   ATTR_DIRECTION_RIGHT: 0}
HOMEKIT_TO_HASS = {c: s for s, c in HASS_TO_HOMEKIT.items()}


@TYPES.register('Fan')
class Fan(HomeAccessory):
    """Generate a Fan accessory for a fan entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args, config):
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_FAN)
        self._domain = split_entity_id(self.entity_id)[0]
        self._flag = {CHAR_ACTIVE: False,
                      CHAR_ROTATION_SPEED: False,
                      CHAR_ROTATION_DIRECTION: False,
                      CHAR_SWING_MODE: False}
        self._state = 0

        self.chars = []
        self._features = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        if self._features & SUPPORT_SET_SPEED:
            self.chars.append(CHAR_ROTATION_SPEED)
            self._speed = None
        if self._features & SUPPORT_DIRECTION:
            self.chars.append(CHAR_ROTATION_DIRECTION)
            self._direction = None
        if self._features & SUPPORT_OSCILLATE:
            self.chars.append(CHAR_SWING_MODE)
            self._oscillating = None

        serv_fan = self.add_preload_service(SERV_FANV2, self.chars)
        self.char_active = serv_fan.configure_char(
            CHAR_ACTIVE, value=self._state, setter_callback=self.set_state)

        if CHAR_ROTATION_SPEED in self.chars:
            speed_list = self.hass.states.get(self.entity_id) \
                .attributes.get(ATTR_SPEED_LIST)
            self.min_step = 100 / len(speed_list) if speed_list else 1
            self.char_speed = serv_fan.configure_char(
                CHAR_ROTATION_SPEED, value=0,
                properties={'minStep': self.min_step},
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
        _LOGGER.debug('%s: Set state to %d', self.entity_id, value)
        self._flag[CHAR_ACTIVE] = True

        service = SERVICE_TURN_ON if value == 1 else SERVICE_TURN_OFF
        self.hass.services.call(self._domain, service,
                                {ATTR_ENTITY_ID: self.entity_id})

    @debounce
    def set_speed(self, value):
        """Set speed if call came from HomeKit."""
        _LOGGER.debug('%s: Set speed to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_SPEED] = True
        if value != 0:
            speed_list = self.hass.states.get(self.entity_id) \
                .attributes.get(ATTR_SPEED_LIST)
            speed = speed_list[int(round(value / self.min_step)) - 1]
            self.hass.components.fan.turn_on(
                self.entity_id, speed=speed)
        else:
            self.hass.components.fan.turn_off(self.entity_id)

    def set_direction(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set direction to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_DIRECTION] = True
        direction = 'left' if value == 1 else 'right'
        self.hass.components.fan.set_direction(self.entity_id,
                                               direction=direction)

    def set_oscillating(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set oscillating to %d', self.entity_id, value)
        self._flag[CHAR_SWING_MODE] = True
        oscillating = True if value == 1 else False
        self.hass.components.fan.oscillate(self.entity_id,
                                           should_oscillate=oscillating)

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
            speed_list = new_state.attributes.get(ATTR_SPEED_LIST)
            speed = new_state.attributes.get(ATTR_SPEED)
            if not self._flag[CHAR_ROTATION_SPEED] and \
                    len(speed_list) > 1 and isinstance(speed, str):
                self._speed = (speed_list.index(speed) + 1) * self.min_step
                if self.char_speed.value != self._speed:
                    self.char_speed.set_value(self._speed)
            self._flag[CHAR_ROTATION_SPEED] = False

        # Handle Direction
        if CHAR_ROTATION_DIRECTION in self.chars:
            direction = new_state.attributes.get(ATTR_DIRECTION)
            if not self._flag[CHAR_ROTATION_DIRECTION] and \
                    direction in HASS_TO_HOMEKIT:
                self._direction = HASS_TO_HOMEKIT[direction]
                if self.char_direction.value != self._direction:
                    self.char_direction.set_value(self._direction)
            self._flag[CHAR_ROTATION_DIRECTION] = False

        # Handle Oscillating
        if CHAR_SWING_MODE in self.chars:
            oscillating = new_state.attributes.get(ATTR_OSCILLATING)
            if not self._flag[CHAR_SWING_MODE] and \
                    oscillating in (True, False):
                self._oscillating = 1 if oscillating else 0
                if self.char_swing.value != self._oscillating:
                    self.char_swing.set_value(self._oscillating)
            self._flag[CHAR_SWING_MODE] = False
