"""Class to hold all light accessories."""
import logging

from pyhap.const import CATEGORY_FAN

from homeassistant.components.fan import (
    ATTR_SPEED, ATTR_SPEED_LIST, SUPPORT_SET_SPEED, SUPPORT_OSCILLATE, SUPPORT_DIRECTION)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_ON, STATE_OFF

from . import TYPES
from .accessories import HomeAccessory, debounce
from .const import (
    SERV_FAN, CHAR_ACTIVE, CHAR_ROTATION_DIRECTION, CHAR_ROTATION_SPEED, CHAR_SWING_MODE)

_LOGGER = logging.getLogger(__name__)


@TYPES.register('Fan')
class Fan(HomeAccessory):
    """Generate a Fan accessory for a fan entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args, config):
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_FAN)
        self._flag = {CHAR_ACTIVE: False}
        self._state = 0

        self.chars = []

        serv_fan = self.add_preload_service(SERV_FAN, self.chars)
        self.char_active = serv_fan.configure_char(
            CHAR_ACTIVE, value=self._state, setter_callback=self.set_state)

    def set_state(self, value):
        """Set state if call came from HomeKit."""
        if self._state == value:
            return

        _LOGGER.debug('%s: Set state to %d', self.entity_id, value)
        self._flag[CHAR_ACTIVE] = True

        if value == 1:
            self.hass.components.fan.turn_on(self.entity_id)
        elif value == 0:
            self.hass.components.fan.turn_off(self.entity_id)

    @debounce
    def set_speed(self, value):
        """Set speed if call came from HomeKit."""
        _LOGGER.debug('%s: Set speed to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_SPEED] = True
        if value != 0:
            self.hass.components.fan.turn_on(
                self.entity_id, speed=value)
        else:
            self.hass.components.fan.turn_off(self.entity_id)

    def update_state(self, new_state):
        """Update light after state change."""
        # Handle State
        state = new_state.state
        if state in (STATE_ON, STATE_OFF):
            self._state = 1 if state == STATE_ON else 0
            if not self._flag[CHAR_ACTIVE] and self.char_active.value != self._state:
                self.char_active.set_value(self._state)
            self._flag[CHAR_ACTIVE] = False
