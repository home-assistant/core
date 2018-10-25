"""Class to hold all switch accessories."""
import logging

from pyhap.const import (
    CATEGORY_FAUCET, CATEGORY_OUTLET, CATEGORY_SHOWER_HEAD,
    CATEGORY_SPRINKLER, CATEGORY_SWITCH)

from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_TYPE, SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON)
from homeassistant.core import split_entity_id

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_ACTIVE, CHAR_IN_USE, CHAR_ON, CHAR_OUTLET_IN_USE, CHAR_VALVE_TYPE,
    SERV_OUTLET, SERV_SWITCH, SERV_VALVE, TYPE_FAUCET, TYPE_SHOWER,
    TYPE_SPRINKLER, TYPE_VALVE)

_LOGGER = logging.getLogger(__name__)

VALVE_TYPE = {
    TYPE_FAUCET: (CATEGORY_FAUCET, 3),
    TYPE_SHOWER: (CATEGORY_SHOWER_HEAD, 2),
    TYPE_SPRINKLER: (CATEGORY_SPRINKLER, 1),
    TYPE_VALVE: (CATEGORY_FAUCET, 0),
}


@TYPES.register('Outlet')
class Outlet(HomeAccessory):
    """Generate an Outlet accessory."""

    def __init__(self, *args):
        """Initialize an Outlet accessory object."""
        super().__init__(*args, category=CATEGORY_OUTLET)
        self._flag_state = False

        serv_outlet = self.add_preload_service(SERV_OUTLET)
        self.char_on = serv_outlet.configure_char(
            CHAR_ON, value=False, setter_callback=self.set_state)
        self.char_outlet_in_use = serv_outlet.configure_char(
            CHAR_OUTLET_IN_USE, value=True)

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s',
                      self.entity_id, value)
        self._flag_state = True
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.call_service(DOMAIN, service, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = (new_state.state == STATE_ON)
        if not self._flag_state:
            _LOGGER.debug('%s: Set current state to %s',
                          self.entity_id, current_state)
            self.char_on.set_value(current_state)
        self._flag_state = False


@TYPES.register('Switch')
class Switch(HomeAccessory):
    """Generate a Switch accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self._domain = split_entity_id(self.entity_id)[0]
        self._flag_state = False

        serv_switch = self.add_preload_service(SERV_SWITCH)
        self.char_on = serv_switch.configure_char(
            CHAR_ON, value=False, setter_callback=self.set_state)

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s',
                      self.entity_id, value)
        self._flag_state = True
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.call_service(self._domain, service, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = (new_state.state == STATE_ON)
        if not self._flag_state:
            _LOGGER.debug('%s: Set current state to %s',
                          self.entity_id, current_state)
            self.char_on.set_value(current_state)
        self._flag_state = False


@TYPES.register('Valve')
class Valve(HomeAccessory):
    """Generate a Valve accessory."""

    def __init__(self, *args):
        """Initialize a Valve accessory object."""
        super().__init__(*args)
        self._flag_state = False
        valve_type = self.config[CONF_TYPE]
        self.category = VALVE_TYPE[valve_type][0]

        serv_valve = self.add_preload_service(SERV_VALVE)
        self.char_active = serv_valve.configure_char(
            CHAR_ACTIVE, value=False, setter_callback=self.set_state)
        self.char_in_use = serv_valve.configure_char(
            CHAR_IN_USE, value=False)
        self.char_valve_type = serv_valve.configure_char(
            CHAR_VALVE_TYPE, value=VALVE_TYPE[valve_type][1])

    def set_state(self, value):
        """Move value state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state to %s',
                      self.entity_id, value)
        self._flag_state = True
        self.char_in_use.set_value(value)
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.call_service(DOMAIN, service, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = (new_state.state == STATE_ON)
        if not self._flag_state:
            _LOGGER.debug('%s: Set current state to %s',
                          self.entity_id, current_state)
            self.char_active.set_value(current_state)
            self.char_in_use.set_value(current_state)
        self._flag_state = False
