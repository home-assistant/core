"""Class to hold all cover accessories."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change

from .accessories import HomeAccessory
from .const import (
    SERVICES_WINDOW_COVERING, CHAR_CURRENT_POSITION,
    CHAR_TARGET_POSITION, CHAR_POSITION_STATE)


_LOGGER = logging.getLogger(__name__)


class Window(HomeAccessory):
    """Generate a Window accessory for a cover entity.

    The cover entity must support: set_cover_position.
    """

    def __init__(self, hass, entity_id, display_name):
        """Initialize a Window accessory object."""
        super().__init__(display_name)
        self.set_category(self.ALL_CATEGORIES.WINDOW)
        self.set_services(SERVICES_WINDOW_COVERING)
        self.set_accessory_info(entity_id)

        self._hass = hass
        self._entity_id = entity_id

        self.current_position = None
        self.homekit_target = None

        self.service_cover = self.get_service(SERVICES_WINDOW_COVERING)
        self.char_current_position = self.service_cover. \
            get_characteristic(CHAR_CURRENT_POSITION)
        self.char_target_position = self.service_cover. \
            get_characteristic(CHAR_TARGET_POSITION)
        self.char_position_state = self.service_cover. \
            get_characteristic(CHAR_POSITION_STATE)

        self.char_target_position.setter_callback = self.move_cover

    def run(self):
        """Method called be object after driver is started."""
        state = self._hass.states.get(self._entity_id)
        self.update_cover_position(new_state=state)

        async_track_state_change(
            self._hass, self._entity_id, self.update_cover_position)

        # self.debug_characteristics()

    def debug_characteristics(self):
        """Method to debug characteristics."""
        while not self.run_sentinel.wait(5):
            _LOGGER.debug("%s: Target: %d", self._entity_id,
                          self.char_target_position.get_value())
            _LOGGER.debug("%s: Current: %d", self._entity_id,
                          self.char_current_position.get_value())
            _LOGGER.debug("%s: PositionState: %d", self._entity_id,
                          self.char_position_state.get_value())

    def move_cover(self, value):
        """Move cover to value if call came from homekit."""
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

    @callback
    def update_cover_position(self, entity_id=None, old_state=None,
                              new_state=None):
        """Update cover position after state changed."""
        if new_state is None:
            return

        self.current_position = int(new_state.attributes['current_position'])
        self.char_current_position.set_value(self.current_position)

        if self.homekit_target is None or \
                abs(self.current_position - self.homekit_target) < 6:
            self.char_target_position.set_value(self.current_position)
            self.char_position_state.set_value(2)
            self.homekit_target = None
