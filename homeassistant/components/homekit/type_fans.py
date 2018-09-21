"""Class to hold all light accessories."""
import logging

from pyhap.const import CATEGORY_FAN

from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, DIRECTION_FORWARD, DIRECTION_REVERSE,
    DOMAIN, SERVICE_OSCILLATE, SERVICE_SET_DIRECTION, SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, STATE_OFF, STATE_ON)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_ACTIVE, CHAR_ROTATION_DIRECTION, CHAR_SWING_MODE, SERV_FANV2)

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
                      CHAR_ROTATION_DIRECTION: False,
                      CHAR_SWING_MODE: False}
        self._state = 0

        self.chars = []
        features = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        if features & SUPPORT_DIRECTION:
            self.chars.append(CHAR_ROTATION_DIRECTION)
        if features & SUPPORT_OSCILLATE:
            self.chars.append(CHAR_SWING_MODE)

        serv_fan = self.add_preload_service(SERV_FANV2, self.chars)
        self.char_active = serv_fan.configure_char(
            CHAR_ACTIVE, value=0, setter_callback=self.set_state)

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
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(DOMAIN, service, params)

    def set_direction(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set direction to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_DIRECTION] = True
        direction = DIRECTION_REVERSE if value == 1 else DIRECTION_FORWARD
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_DIRECTION: direction}
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
