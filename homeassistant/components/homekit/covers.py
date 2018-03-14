"""Class to hold all cover accessories."""
import logging

from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.helpers.event import async_track_state_change

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (
    SERV_WINDOW_COVERING, CHAR_CURRENT_POSITION,
    CHAR_TARGET_POSITION, CHAR_POSITION_STATE)


_LOGGER = logging.getLogger(__name__)


@TYPES.register('Window')
class Window(HomeAccessory):
    """Generate a Window accessory for a cover entity.

    The cover entity must support: set_cover_position.
    """

    def __init__(self, hass, entity_id, display_name):
        """Initialize a Window accessory object."""
        super().__init__(display_name, entity_id, 'WINDOW')

        self._hass = hass
        self._entity_id = entity_id

        self.current_position = None
        self.homekit_target = None

        self.serv_cover = add_preload_service(self, SERV_WINDOW_COVERING)
        self.char_current_position = self.serv_cover. \
            get_characteristic(CHAR_CURRENT_POSITION)
        self.char_target_position = self.serv_cover. \
            get_characteristic(CHAR_TARGET_POSITION)
        self.char_position_state = self.serv_cover. \
            get_characteristic(CHAR_POSITION_STATE)
        self.char_current_position.value = 0
        self.char_target_position.value = 0
        self.char_position_state.value = 0

        self.char_target_position.setter_callback = self.move_cover

    def run(self):
        """Method called be object after driver is started."""
        state = self._hass.states.get(self._entity_id)
        self.update_cover_position(new_state=state)

        async_track_state_change(
            self._hass, self._entity_id, self.update_cover_position)

    def move_cover(self, value):
        """Move cover to value if call came from HomeKit."""
        if value != self.current_position:
            _LOGGER.debug("%s: Set position to %d", self._entity_id, value)
            self.homekit_target = value
            if value > self.current_position:
                self.char_position_state.set_value(1)
            elif value < self.current_position:
                self.char_position_state.set_value(0)
            self._hass.services.call(
                'cover', 'set_cover_position',
                {'entity_id': self._entity_id, 'position': value})

    def update_cover_position(self, entity_id=None, old_state=None,
                              new_state=None):
        """Update cover position after state changed."""
        if new_state is None:
            return

        current_position = new_state.attributes[ATTR_CURRENT_POSITION]
        if current_position is None:
            return
        self.current_position = int(current_position)
        self.char_current_position.set_value(self.current_position)

        if self.homekit_target is None or \
                abs(self.current_position - self.homekit_target) < 6:
            self.char_target_position.set_value(self.current_position)
            self.char_position_state.set_value(2)
            self.homekit_target = None
