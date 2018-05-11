"""Class to hold all light accessories."""
import logging

from pyhap.const import CATEGORY_FAN

from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, ATTR_SPEED, ATTR_SPEED_LIST,
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
    CHAR_SWING_MODE, SERV_FANV2)

_LOGGER = logging.getLogger(__name__)


@TYPES.register('Fan')
class Fan(HomeAccessory):
    """Generate a Fan accessory for a fan entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args, config):
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_FAN)
        self._flag = {CHAR_ACTIVE: False,
                      CHAR_ROTATION_SPEED: False,
                      CHAR_ROTATION_DIRECTION: False,
                      CHAR_SWING_MODE: False}

        self.chars = []
        self._features = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        if self._features & SUPPORT_SET_SPEED:
            self.chars.append(CHAR_ROTATION_SPEED)
        if self._features & SUPPORT_DIRECTION:
            self.chars.append(CHAR_ROTATION_DIRECTION)
        if self._features & SUPPORT_OSCILLATE:
            self.chars.append(CHAR_SWING_MODE)

        serv_fan = self.add_preload_service(SERV_FANV2, self.chars)
        self.char_active = serv_fan.configure_char(
            CHAR_ACTIVE, value=0, setter_callback=self.set_state)

        if CHAR_ROTATION_SPEED in self.chars:
            self.speed_list = self.hass.states.get(self.entity_id) \
                .attributes.get(ATTR_SPEED_LIST)
            self.min_step = 100 / len(self.speed_list) if self.speed_list \
                else 1
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
        self.hass.services.call(DOMAIN, service,
                                {ATTR_ENTITY_ID: self.entity_id})

    @debounce
    def set_speed(self, value):
        """Set speed if call came from HomeKit."""
        _LOGGER.debug('%s: Set speed to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_SPEED] = True
        if value != 0:
            speed = self.speed_list[int(round(value / self.min_step)) - 1]
            self.hass.services.call(DOMAIN, SERVICE_TURN_ON,
                                    {ATTR_ENTITY_ID: self.entity_id,
                                     ATTR_SPEED: speed})
        else:
            self.hass.services.call(DOMAIN, SERVICE_TURN_OFF,
                                    {ATTR_ENTITY_ID: self.entity_id})

    def set_direction(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set direction to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_DIRECTION] = True
        direction = DIRECTION_REVERSE if value == 1 else DIRECTION_FORWARD
        self.hass.services.call(DOMAIN, SERVICE_SET_DIRECTION,
                                {ATTR_ENTITY_ID: self.entity_id,
                                 ATTR_DIRECTION: direction})

    def set_oscillating(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set oscillating to %d', self.entity_id, value)
        self._flag[CHAR_SWING_MODE] = True
        oscillating = 'true' if value == 1 else 'false'
        self.hass.services.call(DOMAIN, SERVICE_OSCILLATE,
                                {ATTR_ENTITY_ID: self.entity_id,
                                 ATTR_OSCILLATING: oscillating})

    def update_state(self, new_state):
        """Update fan after state change."""
        # Handle State
        state = new_state.state
        if state in (STATE_ON, STATE_OFF):
            homekit_state = 1 if state == STATE_ON else 0
            if not self._flag[CHAR_ACTIVE] and \
                    self.char_active.value != homekit_state:
                self.char_active.set_value(homekit_state)
            self._flag[CHAR_ACTIVE] = False

        # Handle Speed
        if CHAR_ROTATION_SPEED in self.chars:
            speed = new_state.attributes.get(ATTR_SPEED)
            if not self._flag[CHAR_ROTATION_SPEED] and \
                    len(self.speed_list) > 1 and isinstance(speed, str):
                homekit_speed = (self.speed_list.index(speed) + 1) * \
                    self.min_step
                if self.char_speed.value != homekit_speed:
                    self.char_speed.set_value(homekit_speed)
            self._flag[CHAR_ROTATION_SPEED] = False

        # Handle Direction
        if CHAR_ROTATION_DIRECTION in self.chars:
            direction = new_state.attributes.get(ATTR_DIRECTION)
            if not self._flag[CHAR_ROTATION_DIRECTION] and \
                    direction in [DIRECTION_FORWARD, DIRECTION_REVERSE]:
                homekit_direction = 1 if direction == DIRECTION_REVERSE else 0
                if self.char_direction.value != homekit_direction:
                    self.char_direction.set_value(homekit_direction)
            self._flag[CHAR_ROTATION_DIRECTION] = False

        # Handle Oscillating
        if CHAR_SWING_MODE in self.chars:
            oscillating = new_state.attributes.get(ATTR_OSCILLATING)
            if not self._flag[CHAR_SWING_MODE] and \
                    oscillating in (True, False):
                homekit_oscillating = 1 if oscillating else 0
                if self.char_swing.value != homekit_oscillating:
                    self.char_swing.set_value(homekit_oscillating)
            self._flag[CHAR_SWING_MODE] = False
