"""Class to hold all cover accessories."""
# pylint: disable=attribute-defined-outside-init
import logging

from homeassistant.components.cover import ATTR_CURRENT_POSITION

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (
    CATEGORY_WINDOW_COVERING, SERV_WINDOW_COVERING,
    CHAR_CURRENT_POSITION, CHAR_TARGET_POSITION, CHAR_POSITION_STATE)

_LOGGER = logging.getLogger(__name__)


@TYPES.register('WindowCovering')
class WindowCovering(HomeAccessory):
    """Generate a Window accessory for a cover entity.

    The cover entity must support: set_cover_position.
    """

    category = CATEGORY_WINDOW_COVERING

    def init_setup(self, config):
        """Initialize a WindowCovering accessory object."""
        self.current_position = None
        self.homekit_target = None

        serv_cover = add_preload_service(self, SERV_WINDOW_COVERING)
        self.char_current_position = serv_cover. \
            get_characteristic(CHAR_CURRENT_POSITION)
        self.char_target_position = serv_cover. \
            get_characteristic(CHAR_TARGET_POSITION)
        self.char_position_state = serv_cover. \
            get_characteristic(CHAR_POSITION_STATE)
        self.char_current_position.value = 0
        self.char_target_position.value = 0
        self.char_position_state.value = 0

        self.char_target_position.setter_callback = self.move_cover

    def move_cover(self, value):
        """Move cover to value if call came from HomeKit."""
        if value != self.current_position:
            _LOGGER.debug('%s: Set position to %d', self.entity_id, value)
            self.homekit_target = value
            if value > self.current_position:
                self.char_position_state.set_value(1)
            elif value < self.current_position:
                self.char_position_state.set_value(0)
            self.hass.components.cover.set_cover_position(
                value, self.entity_id)

    def update_state(self, new_state):
        """Update cover position after state changed."""
        current_position = new_state.attributes.get(ATTR_CURRENT_POSITION)
        if isinstance(current_position, int):
            self.current_position = current_position
            self.char_current_position.set_value(self.current_position)
            if self.homekit_target is None or \
                    abs(self.current_position - self.homekit_target) < 6:
                self.char_target_position.set_value(self.current_position)
                self.char_position_state.set_value(2)
                self.homekit_target = None
