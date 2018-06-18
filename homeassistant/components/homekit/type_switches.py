"""Class to hold all switch accessories."""
import logging

from pyhap.const import CATEGORY_OUTLET, CATEGORY_SWITCH

from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON)
from homeassistant.core import split_entity_id

from . import TYPES
from .accessories import HomeAccessory
from .const import CHAR_ON, CHAR_OUTLET_IN_USE, SERV_OUTLET, SERV_SWITCH

_LOGGER = logging.getLogger(__name__)


@TYPES.register('Outlet')
class Outlet(HomeAccessory):
    """Generate an Outlet accessory."""

    def __init__(self, *args):
        """Initialize an Outlet accessory object."""
        super().__init__(*args, category=CATEGORY_OUTLET)
        self.flag_target_state = False

        serv_outlet = self.add_preload_service(SERV_OUTLET)
        self.char_on = serv_outlet.configure_char(
            CHAR_ON, value=False, setter_callback=self.set_state)
        self.char_outlet_in_use = serv_outlet.configure_char(
            CHAR_OUTLET_IN_USE, value=True)

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s',
                      self.entity_id, value)
        self.flag_target_state = True
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.hass.services.call(DOMAIN, service, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = (new_state.state == STATE_ON)
        if not self.flag_target_state:
            _LOGGER.debug('%s: Set current state to %s',
                          self.entity_id, current_state)
            self.char_on.set_value(current_state)
        self.flag_target_state = False


@TYPES.register('Switch')
class Switch(HomeAccessory):
    """Generate a Switch accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self._domain = split_entity_id(self.entity_id)[0]
        self.flag_target_state = False

        serv_switch = self.add_preload_service(SERV_SWITCH)
        self.char_on = serv_switch.configure_char(
            CHAR_ON, value=False, setter_callback=self.set_state)

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s',
                      self.entity_id, value)
        self.flag_target_state = True
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.hass.services.call(self._domain, service, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = (new_state.state == STATE_ON)
        if not self.flag_target_state:
            _LOGGER.debug('%s: Set current state to %s',
                          self.entity_id, current_state)
            self.char_on.set_value(current_state)
        self.flag_target_state = False
