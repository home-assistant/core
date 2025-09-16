"""Class to hold all switch accessories."""

from __future__ import annotations

import logging
from typing import Any, Final, NamedTuple

from pyhap.characteristic import Characteristic
from pyhap.const import (
    CATEGORY_FAUCET,
    CATEGORY_OUTLET,
    CATEGORY_SHOWER_HEAD,
    CATEGORY_SPRINKLER,
    CATEGORY_SWITCH,
)

from homeassistant.components import button, input_button
from homeassistant.components.input_number import (
    ATTR_VALUE as INPUT_NUMBER_ATTR_VALUE,
    CONF_MAX as INPUT_NUMBER_CONF_MAX,
    CONF_MIN as INPUT_NUMBER_CONF_MIN,
    CONF_STEP as INPUT_NUMBER_CONF_STEP,
    DOMAIN as INPUT_NUMBER_DOMAIN,
    SERVICE_SET_VALUE as INPUT_NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.input_select import ATTR_OPTIONS, SERVICE_SELECT_OPTION
from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_START_MOWING,
    LawnMowerActivity,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_TYPE,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_CLOSING,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .accessories import TYPES, HomeAccessory, HomeDriver
from .const import (
    CHAR_ACTIVE,
    CHAR_CONFIGURED_NAME,
    CHAR_IN_USE,
    CHAR_NAME,
    CHAR_ON,
    CHAR_OUTLET_IN_USE,
    CHAR_REMAINING_DURATION,
    CHAR_SET_DURATION,
    CHAR_VALVE_TYPE,
    CONF_LINKED_VALVE_DURATION,
    CONF_LINKED_VALVE_END_TIME,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
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

VALVE_OPEN_STATES: Final = {STATE_OPEN, STATE_OPENING, STATE_CLOSING}


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

VALVE_LINKED_DURATION_PROPERTIES = {
    INPUT_NUMBER_CONF_MIN,
    INPUT_NUMBER_CONF_MAX,
    INPUT_NUMBER_CONF_STEP,
}

VALVE_DURATION_MIN_DEFAULT = 0
VALVE_DURATION_MAX_DEFAULT = 3600
VALVE_DURATION_STEP_DEFAULT = 1
VALVE_REMAINING_TIME_MAX_DEFAULT = 60 * 60 * 48


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
        self.async_call_service(SWITCH_DOMAIN, service, params)

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
        current_state = new_state.state in (VacuumActivity.CLEANING, STATE_ON)
        _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
        self.char_on.set_value(current_state)


@TYPES.register("LawnMower")
class LawnMower(Switch):
    """Generate a Switch accessory."""

    def set_state(self, value: bool) -> None:
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        state = self.hass.states.get(self.entity_id)
        assert state

        service = SERVICE_START_MOWING if value else SERVICE_DOCK
        self.async_call_service(
            LAWN_MOWER_DOMAIN, service, {ATTR_ENTITY_ID: self.entity_id}
        )

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_state = new_state.state in (LawnMowerActivity.MOWING, STATE_ON)
        _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
        self.char_on.set_value(current_state)


class ValveBase(HomeAccessory):
    """Valve base class."""

    def __init__(
        self,
        valve_type: str,
        open_states: set[str],
        on_service: str,
        off_service: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize a Valve accessory object."""
        super().__init__(*args, **kwargs)
        self.domain = split_entity_id(self.entity_id)[0]
        state = self.hass.states.get(self.entity_id)
        assert state

        self.category = VALVE_TYPE[valve_type].category
        self.open_states = open_states
        self.on_service = on_service
        self.off_service = off_service

        self.chars = []

        self.linked_duration_entity: str | None = self.config.get(
            CONF_LINKED_VALVE_DURATION
        )
        self.linked_end_time_entity: str | None = self.config.get(
            CONF_LINKED_VALVE_END_TIME
        )

        if self.linked_duration_entity:
            self.chars.append(CHAR_SET_DURATION)
        if self.linked_end_time_entity:
            self.chars.append(CHAR_REMAINING_DURATION)

        serv_valve = self.add_preload_service(SERV_VALVE, self.chars)
        self.char_active = serv_valve.configure_char(
            CHAR_ACTIVE, value=False, setter_callback=self.set_state
        )
        self.char_in_use = serv_valve.configure_char(CHAR_IN_USE, value=False)
        self.char_valve_type = serv_valve.configure_char(
            CHAR_VALVE_TYPE, value=VALVE_TYPE[valve_type].valve_type
        )

        if CHAR_SET_DURATION in self.chars:
            _LOGGER.debug(
                "%s: Add characteristic %s", self.entity_id, CHAR_SET_DURATION
            )
            self.char_set_duration = serv_valve.configure_char(
                CHAR_SET_DURATION,
                value=self.get_duration(),
                setter_callback=self.set_duration,
                # Properties are set to match the linked duration entity configuration
                properties={
                    PROP_MIN_VALUE: self._get_linked_duration_property(
                        INPUT_NUMBER_CONF_MIN, VALVE_DURATION_MIN_DEFAULT
                    ),
                    PROP_MAX_VALUE: self._get_linked_duration_property(
                        INPUT_NUMBER_CONF_MAX, VALVE_DURATION_MAX_DEFAULT
                    ),
                    PROP_MIN_STEP: self._get_linked_duration_property(
                        INPUT_NUMBER_CONF_STEP, VALVE_DURATION_STEP_DEFAULT
                    ),
                },
            )

        if CHAR_REMAINING_DURATION in self.chars:
            _LOGGER.debug(
                "%s: Add characteristic %s", self.entity_id, CHAR_REMAINING_DURATION
            )
            self.char_remaining_duration = serv_valve.configure_char(
                CHAR_REMAINING_DURATION,
                getter_callback=self.get_remaining_duration,
                properties={
                    # Default remaining time maxValue to 48 hours if not set via linked default duration.
                    # pyhap truncates the remaining time to maxValue of the characteristic (pyhap default is 1 hour).
                    # This can potentially show a remaining duration that is lower than the actual remaining duration.
                    PROP_MAX_VALUE: self._get_linked_duration_property(
                        INPUT_NUMBER_CONF_MAX, VALVE_REMAINING_TIME_MAX_DEFAULT
                    ),
                },
            )

        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def set_state(self, value: bool) -> None:
        """Move value state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set switch state to %s", self.entity_id, value)
        self.char_in_use.set_value(value)
        params = {ATTR_ENTITY_ID: self.entity_id}
        service = self.on_service if value else self.off_service
        self.async_call_service(self.domain, service, params)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_state = 1 if new_state.state in self.open_states else 0
        _LOGGER.debug("%s: Set active state to %s", self.entity_id, current_state)
        self.char_active.set_value(current_state)
        _LOGGER.debug("%s: Set in_use state to %s", self.entity_id, current_state)
        self.char_in_use.set_value(current_state)
        self._update_duration_chars()

    def _update_duration_chars(self) -> None:
        """Update valve duration related properties if characteristics are available."""
        if CHAR_SET_DURATION in self.chars:
            self.char_set_duration.set_value(self.get_duration())
        if CHAR_REMAINING_DURATION in self.chars:
            self.char_remaining_duration.set_value(self.get_remaining_duration())

    def set_duration(self, value: int) -> None:
        """Set default duration for how long the valve should remain open."""
        _LOGGER.debug("%s: Set default run time to %s", self.entity_id, value)
        self.async_call_service(
            INPUT_NUMBER_DOMAIN,
            INPUT_NUMBER_SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: self.linked_duration_entity,
                INPUT_NUMBER_ATTR_VALUE: value,
            },
            value,
        )

    def get_duration(self) -> int:
        """Get the default duration from Home Assistant."""
        duration_state = self._get_entity_state(self.linked_duration_entity)
        if duration_state is None:
            _LOGGER.debug(
                "%s: No linked duration entity state available", self.entity_id
            )
            return 0

        try:
            duration = float(duration_state)
            return max(int(duration), 0)
        except ValueError:
            _LOGGER.debug("%s: Cannot parse linked duration entity", self.entity_id)
            return 0

    def get_remaining_duration(self) -> int:
        """Calculate the remaining duration based on end time in Home Assistant."""
        end_time_state = self._get_entity_state(self.linked_end_time_entity)
        if end_time_state is None:
            _LOGGER.debug(
                "%s: No linked end time entity state available", self.entity_id
            )
            return self.get_duration() if self.char_in_use.value else 0

        end_time = dt_util.parse_datetime(end_time_state)
        if end_time is None:
            _LOGGER.debug("%s: Cannot parse linked end time entity", self.entity_id)
            return self.get_duration() if self.char_in_use.value else 0

        remaining_time = (end_time - dt_util.utcnow()).total_seconds()
        return max(int(remaining_time), 0)

    def _get_entity_state(self, entity_id: str | None) -> str | None:
        """Fetch the state of a linked entity."""
        if entity_id is None:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        return state.state

    def _get_linked_duration_property(self, attr: str, fallback_value: int) -> int:
        """Get property from linked duration entity attribute."""
        if attr not in VALVE_LINKED_DURATION_PROPERTIES:
            return fallback_value
        if self.linked_duration_entity is None:
            return fallback_value
        state = self.hass.states.get(self.linked_duration_entity)
        if state is None:
            return fallback_value
        attr_value = state.attributes.get(attr, fallback_value)
        if attr_value is None:
            return fallback_value
        return int(attr_value)


@TYPES.register("ValveSwitch")
class ValveSwitch(ValveBase):
    """Generate a Valve accessory from a HomeAssistant switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        driver: HomeDriver,
        name: str,
        entity_id: str,
        aid: int,
        config: dict[str, Any],
        *args: Any,
    ) -> None:
        """Initialize a Valve accessory object."""
        super().__init__(
            config[CONF_TYPE],
            {STATE_ON},
            SERVICE_TURN_ON,
            SERVICE_TURN_OFF,
            hass,
            driver,
            name,
            entity_id,
            aid,
            config,
            *args,
        )


@TYPES.register("Valve")
class Valve(ValveBase):
    """Generate a Valve accessory from a HomeAssistant valve."""

    def __init__(self, *args: Any) -> None:
        """Initialize a Valve accessory object."""
        super().__init__(
            TYPE_VALVE,
            VALVE_OPEN_STATES,
            SERVICE_OPEN_VALVE,
            SERVICE_CLOSE_VALVE,
            *args,
        )


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
                SERV_OUTLET,
                [CHAR_NAME, CHAR_CONFIGURED_NAME, CHAR_IN_USE],
                unique_id=option,
            )
            name = cleanup_name_for_homekit(option)
            serv_option.configure_char(CHAR_NAME, value=name)
            serv_option.configure_char(CHAR_CONFIGURED_NAME, value=name)
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
