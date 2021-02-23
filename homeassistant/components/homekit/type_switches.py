"""Class to hold all switch accessories."""
import logging

from pyhap.const import (
    CATEGORY_FAUCET,
    CATEGORY_OUTLET,
    CATEGORY_SHOWER_HEAD,
    CATEGORY_SPRINKLER,
    CATEGORY_SWITCH,
)

from homeassistant.components.switch import DOMAIN
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    STATE_CLEANING,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_TYPE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import callback, split_entity_id
from homeassistant.helpers.event import call_later

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_IN_USE,
    CHAR_ON,
    CHAR_OUTLET_IN_USE,
    CHAR_VALVE_TYPE,
    SERV_OUTLET,
    SERV_SWITCH,
    SERV_VALVE,
    TYPE_FAUCET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_VALVE,
)

_LOGGER = logging.getLogger(__name__)

VALVE_TYPE = {
    TYPE_FAUCET: (CATEGORY_FAUCET, 3),
    TYPE_SHOWER: (CATEGORY_SHOWER_HEAD, 2),
    TYPE_SPRINKLER: (CATEGORY_SPRINKLER, 1),
    TYPE_VALVE: (CATEGORY_FAUCET, 0),
}


@TYPES.register("Outlet")
class Outlet(HomeAccessory):
    """Generate an Outlet accessory."""

    def __init__(self, *args):
        """Initialize an Outlet accessory object."""
        super().__init__(*args, category=CATEGORY_OUTLET)
        state = self.hass.states.get(self.entity_id)

        serv_outlet = self.add_preload_service(SERV_OUTLET)
        self.char_on = serv_outlet.configure_char(
            CHAR_ON, value=False, setter_callback=self.set_state
        )
        self.char_outlet_in_use = serv_outlet.configure_char(
            CHAR_OUTLET_IN_USE, value=True
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.async_call_service(DOMAIN, service, params)

    @callback
    def async_update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state == STATE_ON
        if self.char_on.value is not current_state:
            _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
            self.char_on.set_value(current_state)


@TYPES.register("Switch")
class Switch(HomeAccessory):
    """Generate a Switch accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self._domain = split_entity_id(self.entity_id)[0]
        state = self.hass.states.get(self.entity_id)

        self.activate_only = self.is_activate(self.hass.states.get(self.entity_id))

        serv_switch = self.add_preload_service(SERV_SWITCH)
        self.char_on = serv_switch.configure_char(
            CHAR_ON, value=False, setter_callback=self.set_state
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def is_activate(self, state):
        """Check if entity is activate only."""
        if self._domain == "scene":
            return True
        return False

    def reset_switch(self, *args):
        """Reset switch to emulate activate click."""
        _LOGGER.debug("%s: Reset switch to off", self.entity_id)
        if self.char_on.value is not False:
            self.char_on.set_value(False)

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        if self.activate_only and not value:
            _LOGGER.debug("%s: Ignoring turn_off call", self.entity_id)
            return
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.async_call_service(self._domain, service, params)

        if self.activate_only:
            call_later(self.hass, 1, self.reset_switch)

    @callback
    def async_update_state(self, new_state):
        """Update switch state after state changed."""
        self.activate_only = self.is_activate(new_state)
        if self.activate_only:
            _LOGGER.debug(
                "%s: Ignore state change, entity is activate only", self.entity_id
            )
            return

        current_state = new_state.state == STATE_ON
        if self.char_on.value is not current_state:
            _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
            self.char_on.set_value(current_state)


@TYPES.register("Vacuum")
class Vacuum(Switch):
    """Generate a Switch accessory."""

    def set_state(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        state = self.hass.states.get(self.entity_id)
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if value:
            sup_start = features & SUPPORT_START
            service = SERVICE_START if sup_start else SERVICE_TURN_ON
        else:
            sup_return_home = features & SUPPORT_RETURN_HOME
            service = SERVICE_RETURN_TO_BASE if sup_return_home else SERVICE_TURN_OFF

        self.async_call_service(
            VACUUM_DOMAIN, service, {ATTR_ENTITY_ID: self.entity_id}
        )

    @callback
    def async_update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state in (STATE_CLEANING, STATE_ON)
        if self.char_on.value is not current_state:
            _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
            self.char_on.set_value(current_state)


@TYPES.register("Valve")
class Valve(HomeAccessory):
    """Generate a Valve accessory."""

    def __init__(self, *args):
        """Initialize a Valve accessory object."""
        super().__init__(*args)
        state = self.hass.states.get(self.entity_id)
        valve_type = self.config[CONF_TYPE]
        self.category = VALVE_TYPE[valve_type][0]

        serv_valve = self.add_preload_service(SERV_VALVE)
        self.char_active = serv_valve.configure_char(
            CHAR_ACTIVE, value=False, setter_callback=self.set_state
        )
        self.char_in_use = serv_valve.configure_char(CHAR_IN_USE, value=False)
        self.char_valve_type = serv_valve.configure_char(
            CHAR_VALVE_TYPE, value=VALVE_TYPE[valve_type][1]
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def set_state(self, value):
        """Move value state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        self.char_in_use.set_value(value)
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.async_call_service(DOMAIN, service, params)

    @callback
    def async_update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = 1 if new_state.state == STATE_ON else 0
        if self.char_active.value != current_state:
            _LOGGER.debug("%s: Set active state to %s", self.entity_id, current_state)
            self.char_active.set_value(current_state)
        if self.char_in_use.value != current_state:
            _LOGGER.debug("%s: Set in_use state to %s", self.entity_id, current_state)
            self.char_in_use.set_value(current_state)
