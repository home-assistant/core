"""Class to hold all switch accessories."""
import logging

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON)
from homeassistant.core import split_entity_id

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import CATEGORY_SWITCH, SERV_SWITCH, CHAR_ON

_LOGGER = logging.getLogger(__name__)


@TYPES.register('Switch')
class Switch(HomeAccessory):
    """Generate a Switch accessory."""

    def __init__(self, hass, entity_id, display_name, **kwargs):
        """Initialize a Switch accessory object to represent a remote."""
        super().__init__(display_name, entity_id, CATEGORY_SWITCH, **kwargs)

        self.hass = hass
        self.entity_id = entity_id
        self._domain = split_entity_id(entity_id)[0]

        self.flag_target_state = False

        serv_switch = add_preload_service(self, SERV_SWITCH)
        self.char_on = serv_switch.get_characteristic(CHAR_ON)
        self.char_on.value = False
        self.char_on.setter_callback = self.set_state

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s',
                      self.entity_id, value)
        self.flag_target_state = True
        self.char_on.set_value(value, should_callback=False)
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.hass.services.call(self._domain, service,
                                {ATTR_ENTITY_ID: self.entity_id})

    def update_state(self, entity_id=None, old_state=None, new_state=None):
        """Update switch state after state changed."""
        if new_state is None:
            return

        current_state = (new_state.state == STATE_ON)
        if not self.flag_target_state:
            _LOGGER.debug('%s: Set current state to %s',
                          self.entity_id, current_state)
            self.char_on.set_value(current_state, should_callback=False)

        self.flag_target_state = False
