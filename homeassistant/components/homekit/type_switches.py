"""Class to hold all switch accessories."""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

from pyhap.characteristic import Characteristic
from pyhap.const import (
    CATEGORY_FAUCET,
    CATEGORY_OUTLET,
    CATEGORY_SHOWER_HEAD,
    CATEGORY_SPRINKLER,
    CATEGORY_SWITCH,
)

from homeassistant.components import button, input_button
from homeassistant.components.input_select import ATTR_OPTIONS, SERVICE_SELECT_OPTION
from homeassistant.components.switch import DOMAIN
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    STATE_CLEANING,
    VacuumEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_TYPE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import State, callback, split_entity_id
from homeassistant.helpers.event import async_call_later

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_IN_USE,
    CHAR_NAME,
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
from .util import cleanup_name_for_homekit

_LOGGER = logging.getLogger(__name__)


class ValveInfo(NamedTuple):
    """Category and type information for valve."""

    category: int
    valve_type: int


VALVE_TYPE: dict[str, ValveInfo] = {
    TYPE_FAUCET: ValveInfo(CATEGORY_FAUCET, 3),
    TYPE_SHOWER: ValveInfo(CATEGORY_SHOWER_HEAD, 2),
    TYPE_SPRINKLER: ValveInfo(CATEGORY_SPRINKLER, 1),
    TYPE_VALVE: ValveInfo(CATEGORY_FAUCET, 0),
}


ACTIVATE_ONLY_SWITCH_DOMAINS = {"button", "input_button", "scene", "script"}

ACTIVATE_ONLY_RESET_SECONDS = 10


@TYPES.register("Outlet")
class Outlet(HomeAccessory):
    """Generate an Outlet accessory."""

    def __init__(self, *args: Any) -> None:
        """Initialize an Outlet accessory object."""
        super().__init__(*args, category=CATEGORY_OUTLET)
        state = self.hass.states.get(self.entity_id)
        assert state

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

    def set_state(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.async_call_service(DOMAIN, service, params)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_state = new_state.state == STATE_ON
        _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
        self.char_on.set_value(current_state)


@TYPES.register("Switch")
class Switch(HomeAccessory):
    """Generate a Switch accessory."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self._domain, self._object_id = split_entity_id(self.entity_id)
        state = self.hass.states.get(self.entity_id)
        assert state

        self.activate_only = self.is_activate(state)

        serv_switch = self.add_preload_service(SERV_SWITCH)
        self.char_on = serv_switch.configure_char(
            CHAR_ON, value=False, setter_callback=self.set_state
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def is_activate(self, state: State) -> bool:
        """Check if entity is activate only."""
        return self._domain in ACTIVATE_ONLY_SWITCH_DOMAINS

    def reset_switch(self, *args: Any) -> None:
        """Reset switch to emulate activate click."""
        _LOGGER.debug("%s: Reset switch to off", self.entity_id)
        self.char_on.set_value(False)

    def set_state(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        if self.activate_only and not value:
            _LOGGER.debug("%s: Ignoring turn_off call", self.entity_id)
            return

        params = {ATTR_ENTITY_ID: self.entity_id}
        if self._domain == "script":
            service = self._object_id
            params = {}
        elif self._domain == button.DOMAIN:
            service = button.SERVICE_PRESS
        elif self._domain == input_button.DOMAIN:
            service = input_button.SERVICE_PRESS
        else:
            service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF

        self.async_call_service(self._domain, service, params)

        if self.activate_only:
            async_call_later(self.hass, ACTIVATE_ONLY_RESET_SECONDS, self.reset_switch)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        self.activate_only = self.is_activate(new_state)
        if self.activate_only:
            _LOGGER.debug(
                "%s: Ignore state change, entity is activate only", self.entity_id
            )
            return

        current_state = new_state.state == STATE_ON
        _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
        self.char_on.set_value(current_state)


@TYPES.register("Vacuum")
class Vacuum(Switch):
    """Generate a Switch accessory."""

    def set_state(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        state = self.hass.states.get(self.entity_id)
        assert state

        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if value:
            sup_start = features & VacuumEntityFeature.START
            service = SERVICE_START if sup_start else SERVICE_TURN_ON
        else:
            sup_return_home = features & VacuumEntityFeature.RETURN_HOME
            service = SERVICE_RETURN_TO_BASE if sup_return_home else SERVICE_TURN_OFF

        self.async_call_service(
            VACUUM_DOMAIN, service, {ATTR_ENTITY_ID: self.entity_id}
        )

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_state = new_state.state in (STATE_CLEANING, STATE_ON)
        _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
        self.char_on.set_value(current_state)


@TYPES.register("Valve")
class Valve(HomeAccessory):
    """Generate a Valve accessory."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Valve accessory object."""
        super().__init__(*args)
        state = self.hass.states.get(self.entity_id)
        assert state

        valve_type = self.config[CONF_TYPE]
        self.category = VALVE_TYPE[valve_type].category

        serv_valve = self.add_preload_service(SERV_VALVE)
        self.char_active = serv_valve.configure_char(
            CHAR_ACTIVE, value=False, setter_callback=self.set_state
        )
        self.char_in_use = serv_valve.configure_char(CHAR_IN_USE, value=False)
        self.char_valve_type = serv_valve.configure_char(
            CHAR_VALVE_TYPE, value=VALVE_TYPE[valve_type].valve_type
        )
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def set_state(self, value: bool) -> None:
        """Move value state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        self.char_in_use.set_value(value)
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
        self.async_call_service(DOMAIN, service, params)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_state = 1 if new_state.state == STATE_ON else 0
        _LOGGER.debug("%s: Set active state to %s", self.entity_id, current_state)
        self.char_active.set_value(current_state)
        _LOGGER.debug("%s: Set in_use state to %s", self.entity_id, current_state)
        self.char_in_use.set_value(current_state)


@TYPES.register("SelectSwitch")
class SelectSwitch(HomeAccessory):
    """Generate a Switch accessory that contains multiple switches."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        self.domain = split_entity_id(self.entity_id)[0]
        state = self.hass.states.get(self.entity_id)
        assert state

        self.select_chars: dict[str, Characteristic] = {}
        options = state.attributes[ATTR_OPTIONS]
        for option in options:
            serv_option = self.add_preload_service(
                SERV_OUTLET, [CHAR_NAME, CHAR_IN_USE], unique_id=option
            )
            serv_option.configure_char(
                CHAR_NAME, value=cleanup_name_for_homekit(option)
            )
            serv_option.configure_char(CHAR_IN_USE, value=False)
            self.select_chars[option] = serv_option.configure_char(
                CHAR_ON,
                value=False,
                setter_callback=lambda value, option=option: self.select_option(option),
            )
        self.set_primary_service(self.select_chars[options[0]])
        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def select_option(self, option: str) -> None:
        """Set option from HomeKit."""
        _LOGGER.debug("%s: Set option to %s", self.entity_id, option)
        params = {ATTR_ENTITY_ID: self.entity_id, "option": option}
        self.async_call_service(self.domain, SERVICE_SELECT_OPTION, params)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_option = cleanup_name_for_homekit(new_state.state)
        for option, char in self.select_chars.items():
            char.set_value(option == current_option)
