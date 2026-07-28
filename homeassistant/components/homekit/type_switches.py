"""Class to hold all switch accessories."""

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any, Final, NamedTuple, override

from pyhap.characteristic import Characteristic
from pyhap.const import (
    CATEGORY_FAUCET,
    CATEGORY_OUTLET,
    CATEGORY_SHOWER_HEAD,
    CATEGORY_SPRINKLER,
    CATEGORY_SWITCH,
)
from pyhap.util import callback as pyhap_callback

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
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HassJobType,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .accessories import TYPES, HomeAccessory, HomeDriver
from .const import (
    CHAR_ACTIVE,
    CHAR_CONFIGURED_NAME,
    CHAR_IN_USE,
    CHAR_IS_CONFIGURED,
    CHAR_NAME,
    CHAR_ON,
    CHAR_OUTLET_IN_USE,
    CHAR_PROGRAM_MODE,
    CHAR_REMAINING_DURATION,
    CHAR_SERVICE_LABEL_INDEX,
    CHAR_SERVICE_LABEL_NAMESPACE,
    CHAR_SET_DURATION,
    CHAR_STATUS_FAULT,
    CHAR_VALVE_TYPE,
    CONF_LINKED_IRRIGATION_VALVES,
    CONF_LINKED_VALVE_DURATION,
    CONF_LINKED_VALVE_END_TIME,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
    SERV_IRRIGATION_SYSTEM,
    SERV_OUTLET,
    SERV_SERVICE_LABEL,
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
    @override
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
    @override
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

    @override
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
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_state = new_state.state in (VacuumActivity.CLEANING, STATE_ON)
        _LOGGER.debug("%s: Set current state to %s", self.entity_id, current_state)
        self.char_on.set_value(current_state)


@TYPES.register("LawnMower")
class LawnMower(Switch):
    """Generate a Switch accessory."""

    @override
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
    @override
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
                    # Default remaining time maxValue to 48 hours
                    # if not set via linked default duration.
                    # pyhap truncates the remaining time to
                    # maxValue of the characteristic (pyhap
                    # default is 1 hour). This can potentially
                    # show a remaining duration that is lower
                    # than the actual remaining duration.
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
    @override
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
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update switch state after state changed."""
        current_option = new_state.state
        for option, char in self.select_chars.items():
            char.set_value(option == current_option)


HK_VALVE_TYPE_IRRIGATION = 1
HK_PROGRAM_MODE_NO_PROGRAM_SCHEDULED = 0
HK_IS_CONFIGURED = 1
HK_STATUS_FAULT_NO_FAULT = 0
HK_STATUS_FAULT_GENERAL_FAULT = 1
HK_SERVICE_LABEL_NAMESPACE_ARABIC_NUMERALS = 1

IRRIGATION_DEFAULT_DURATION = 300
IRRIGATION_DURATION_MAX = 86400

IRRIGATION_DURATION_PROPERTIES = {
    PROP_MIN_VALUE: 0,
    PROP_MAX_VALUE: IRRIGATION_DURATION_MAX,
    PROP_MIN_STEP: 1,
}


@TYPES.register("IrrigationSystem")
class IrrigationSystem(HomeAccessory):
    """Generate an IrrigationSystem accessory grouping multiple valve entities."""

    def __init__(self, *args: Any) -> None:
        """Initialize an IrrigationSystem accessory."""
        super().__init__(*args, category=CATEGORY_SPRINKLER)
        state = self.hass.states.get(self.entity_id)
        assert state

        self._valve_entity_ids: list[str] = [
            self.entity_id,
            *self.config.get(CONF_LINKED_IRRIGATION_VALVES, []),
        ]
        self._valve_chars: dict[str, dict[str, Any]] = {}

        serv_irrigation = self.add_preload_service(
            SERV_IRRIGATION_SYSTEM,
            [CHAR_NAME, CHAR_REMAINING_DURATION, CHAR_STATUS_FAULT],
        )
        serv_irrigation.configure_char(CHAR_NAME, value=self.display_name)
        self._char_system_active = serv_irrigation.configure_char(
            CHAR_ACTIVE,
            value=False,
            setter_callback=self._set_system_active,
        )
        self._char_system_in_use = serv_irrigation.configure_char(
            CHAR_IN_USE, value=False
        )
        self._char_program_mode = serv_irrigation.configure_char(
            CHAR_PROGRAM_MODE,
            value=HK_PROGRAM_MODE_NO_PROGRAM_SCHEDULED,
        )
        self._char_system_remaining = serv_irrigation.configure_char(
            CHAR_REMAINING_DURATION,
            value=0,
            properties=IRRIGATION_DURATION_PROPERTIES,
        )
        self._char_system_status_fault = serv_irrigation.configure_char(
            CHAR_STATUS_FAULT,
            value=HK_STATUS_FAULT_NO_FAULT,
        )
        serv_service_label = self.add_preload_service(
            SERV_SERVICE_LABEL,
            [CHAR_SERVICE_LABEL_NAMESPACE],
        )
        serv_service_label.configure_char(
            CHAR_SERVICE_LABEL_NAMESPACE,
            value=HK_SERVICE_LABEL_NAMESPACE_ARABIC_NUMERALS,
        )

        for index, entity_id in enumerate(self._valve_entity_ids, start=1):
            valve_state = self.hass.states.get(entity_id)
            friendly = (
                valve_state.attributes.get(ATTR_FRIENDLY_NAME) if valve_state else None
            )
            name = cleanup_name_for_homekit(friendly or entity_id)
            initial_duration = self._duration_from_state(valve_state)
            if initial_duration is None:
                initial_duration = IRRIGATION_DEFAULT_DURATION
            initial_remaining = self._remaining_from_state(valve_state)
            serv_valve = self.add_preload_service(
                SERV_VALVE,
                [
                    CHAR_NAME,
                    CHAR_CONFIGURED_NAME,
                    CHAR_SET_DURATION,
                    CHAR_REMAINING_DURATION,
                    CHAR_IS_CONFIGURED,
                    CHAR_SERVICE_LABEL_INDEX,
                    CHAR_STATUS_FAULT,
                ],
                unique_id=entity_id,
            )
            serv_valve.configure_char(CHAR_NAME, value=name)
            serv_valve.configure_char(CHAR_CONFIGURED_NAME, value=name)
            serv_valve.configure_char(CHAR_IS_CONFIGURED, value=HK_IS_CONFIGURED)
            serv_valve.configure_char(CHAR_SERVICE_LABEL_INDEX, value=index)
            char_active = serv_valve.configure_char(
                CHAR_ACTIVE,
                value=False,
                setter_callback=lambda v, eid=entity_id: self._set_valve_active(eid, v),
            )
            char_in_use = serv_valve.configure_char(CHAR_IN_USE, value=False)
            serv_valve.configure_char(CHAR_VALVE_TYPE, value=HK_VALVE_TYPE_IRRIGATION)
            char_status_fault = serv_valve.configure_char(
                CHAR_STATUS_FAULT,
                value=HK_STATUS_FAULT_NO_FAULT,
            )
            char_set_duration = serv_valve.configure_char(
                CHAR_SET_DURATION,
                value=initial_duration,
                properties=IRRIGATION_DURATION_PROPERTIES,
                setter_callback=lambda v, eid=entity_id: self._set_valve_duration(
                    eid, v
                ),
            )
            char_remaining = serv_valve.configure_char(
                CHAR_REMAINING_DURATION,
                value=initial_remaining,
                properties=IRRIGATION_DURATION_PROPERTIES,
            )
            self._valve_chars[entity_id] = {
                CHAR_ACTIVE: char_active,
                CHAR_IN_USE: char_in_use,
                CHAR_SET_DURATION: char_set_duration,
                CHAR_REMAINING_DURATION: char_remaining,
                CHAR_STATUS_FAULT: char_status_fault,
                "duration": initial_duration,
                "end_time": None,
                "close_timer": None,
                "update_timer": None,
            }
            serv_irrigation.add_linked_service(serv_valve)
            serv_valve.add_linked_service(serv_service_label)

        for entity_id in self._valve_entity_ids:
            if valve_state := self.hass.states.get(entity_id):
                self._sync_valve_chars(entity_id, valve_state)
            else:
                self._set_valve_unavailable(entity_id)
        self._update_system_state()

    @callback
    @pyhap_callback  # type: ignore[untyped-decorator]
    @override
    def run(self) -> None:
        """Handle accessory driver start; subscribe to all linked valve entities."""
        super().run()
        linked_valve_ids = self._valve_entity_ids[1:]
        if linked_valve_ids:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    linked_valve_ids,
                    self._async_linked_valve_state_changed,
                    job_type=HassJobType.Callback,
                )
            )
            for entity_id in linked_valve_ids:
                if valve_state := self.hass.states.get(entity_id):
                    self._sync_valve_chars(entity_id, valve_state)
                else:
                    self._set_valve_unavailable(entity_id)
        self._update_system_state()

    @callback
    def _async_linked_valve_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state changes for linked (non-primary) valve entities."""
        new_state = event.data["new_state"]
        if new_state is None:
            if old_state := event.data["old_state"]:
                self._set_valve_unavailable(old_state.entity_id)
            else:
                self._set_valve_unavailable(event.data["entity_id"])
            self._update_system_state()
            return
        self._sync_valve_chars(new_state.entity_id, new_state)
        self._update_system_state()

    @callback
    @override
    def async_update_state_callback(self, new_state: State | None) -> None:
        """Handle primary valve state changes, including unavailable/unknown."""
        if new_state is None:
            self._set_valve_unavailable(self.entity_id)
            self._update_system_state()
            return
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._sync_valve_chars(self.entity_id, new_state)
            self._update_system_state()
            return
        super().async_update_state_callback(new_state)

    @callback
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update primary valve entity state from HA."""
        self._sync_valve_chars(self.entity_id, new_state)
        self._update_system_state()

    def _sync_valve_chars(self, entity_id: str, state: State) -> None:
        """Sync HomeKit characteristics from HA state for one valve."""
        chars = self._valve_chars.get(entity_id)
        if chars is None:
            return
        has_fault = state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        chars[CHAR_STATUS_FAULT].set_value(
            HK_STATUS_FAULT_GENERAL_FAULT if has_fault else HK_STATUS_FAULT_NO_FAULT
        )
        if has_fault:
            self._set_valve_inactive(entity_id)
            self._clear_local_runtime(entity_id)
            return
        is_open = state.state in VALVE_OPEN_STATES
        chars[CHAR_ACTIVE].set_value(int(is_open))
        chars[CHAR_IN_USE].set_value(int(is_open))
        if (device_duration := self._duration_from_state(state)) is not None and (
            device_duration != chars["duration"]
        ):
            chars["duration"] = device_duration
            chars[CHAR_SET_DURATION].set_value(device_duration)
        remaining = self._remaining_from_state(state)
        if is_open:
            if remaining > 0:
                self._clear_local_runtime(entity_id)
            elif (local_remaining := self._remaining_from_local_runtime(entity_id)) > 0:
                remaining = local_remaining
            else:
                self._start_local_runtime(entity_id, chars["duration"])
                remaining = self._remaining_from_local_runtime(entity_id)
        else:
            self._clear_local_runtime(entity_id)
        chars[CHAR_REMAINING_DURATION].set_value(remaining)

    def _update_system_state(self) -> None:
        """Update IrrigationSystem-level Active/InUse from child valve states."""
        any_active = any(
            chars[CHAR_IN_USE].value for chars in self._valve_chars.values()
        )
        remaining = max(
            int(chars[CHAR_REMAINING_DURATION].value or 0)
            for chars in self._valve_chars.values()
        )
        any_fault = any(
            chars[CHAR_STATUS_FAULT].value == HK_STATUS_FAULT_GENERAL_FAULT
            for chars in self._valve_chars.values()
        )
        self._char_system_active.set_value(int(any_active))
        self._char_system_in_use.set_value(int(any_active))
        self._char_system_remaining.set_value(remaining)
        self._char_system_status_fault.set_value(
            HK_STATUS_FAULT_GENERAL_FAULT if any_fault else HK_STATUS_FAULT_NO_FAULT
        )

    def _set_system_active(self, value: int) -> None:
        """Close all valves when HomeKit deactivates the irrigation system."""
        if not value:
            for entity_id in self._valve_entity_ids:
                self.hass.async_create_task(
                    self._async_call_valve_service_and_resync(
                        entity_id, SERVICE_CLOSE_VALVE, value
                    ),
                    eager_start=True,
                )
        self._update_system_state()

    def _set_valve_active(self, entity_id: str, value: int) -> None:
        """Open or close a specific valve when HomeKit commands it."""
        service = SERVICE_OPEN_VALVE if value else SERVICE_CLOSE_VALVE
        chars = self._valve_chars.get(entity_id)
        if chars:
            chars[CHAR_IN_USE].set_value(int(value))
            chars[CHAR_ACTIVE].set_value(int(value))
            chars[CHAR_REMAINING_DURATION].set_value(chars["duration"] if value else 0)
        if value:
            self._start_local_runtime(entity_id, chars["duration"] if chars else 0)
        else:
            self._clear_local_runtime(entity_id)
        self.hass.async_create_task(
            self._async_call_valve_service_and_resync(entity_id, service, value),
            eager_start=True,
        )
        self._update_system_state()

    def _set_valve_duration(self, entity_id: str, value: int) -> None:
        """Store the HomeKit-requested run duration for a valve."""
        chars = self._valve_chars.get(entity_id)
        if chars:
            chars["duration"] = max(int(value), 0)
            chars[CHAR_SET_DURATION].set_value(chars["duration"])

    def _duration_from_state(self, state: State | None) -> int | None:
        """Get a valve duration from state attributes when provided by the device."""
        if state is None:
            return None
        for key in ("set_duration", "duration", "default_duration"):
            if (raw := state.attributes.get(key)) is not None:
                try:
                    return max(int(float(raw)), 0)
                except TypeError, ValueError:
                    continue
        return None

    def _remaining_from_state(self, state: State | None) -> int:
        """Get remaining duration from state attributes when provided by the device."""
        if state is None:
            return 0
        for key in ("remaining_duration", "remaining", "remaining_time"):
            if (raw := state.attributes.get(key)) is not None:
                try:
                    return max(int(float(raw)), 0)
                except TypeError, ValueError:
                    continue
        if (end_time_raw := state.attributes.get("end_time")) is not None:
            if (end_time := dt_util.parse_datetime(str(end_time_raw))) is not None:
                return max(int((end_time - dt_util.utcnow()).total_seconds()), 0)
        return 0

    async def _async_call_valve_service_and_resync(
        self, entity_id: str, service: str, value: int
    ) -> None:
        """Call valve service and re-sync the commanded valve on failure."""
        success = await self.async_call_service_and_wait(
            VALVE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            value,
        )
        if success:
            return
        self._clear_local_runtime(entity_id)
        if state := self.hass.states.get(entity_id):
            self._sync_valve_chars(entity_id, state)
        else:
            self._set_valve_unavailable(entity_id)
        self._update_system_state()

    def _set_valve_unavailable(self, entity_id: str) -> None:
        """Set zone characteristics to faulted/unavailable."""
        chars = self._valve_chars.get(entity_id)
        if chars is None:
            return
        chars[CHAR_STATUS_FAULT].set_value(HK_STATUS_FAULT_GENERAL_FAULT)
        self._set_valve_inactive(entity_id)
        self._clear_local_runtime(entity_id)

    def _set_valve_inactive(self, entity_id: str) -> None:
        """Set zone active/in-use/remaining to inactive values."""
        if chars := self._valve_chars.get(entity_id):
            chars[CHAR_ACTIVE].set_value(0)
            chars[CHAR_IN_USE].set_value(0)
            chars[CHAR_REMAINING_DURATION].set_value(0)

    def _start_local_runtime(self, entity_id: str, duration: int) -> None:
        """Start local countdown/auto-close for a zone."""
        chars = self._valve_chars.get(entity_id)
        if chars is None:
            return
        self._clear_local_runtime(entity_id)
        seconds = max(int(duration), 0)
        if seconds <= 0:
            return
        chars["end_time"] = dt_util.utcnow() + timedelta(seconds=seconds)
        chars["close_timer"] = async_call_later(
            self.hass,
            seconds,
            self._make_close_runtime_callback(entity_id),
        )
        chars["update_timer"] = async_call_later(
            self.hass,
            1,
            self._make_update_runtime_callback(entity_id),
        )

    @callback
    def _async_local_runtime_close(self, entity_id: str) -> None:
        """Close a zone when local runtime reaches zero."""
        if chars := self._valve_chars.get(entity_id):
            chars["close_timer"] = None
        self._set_valve_active(entity_id, 0)

    @callback
    def _update_local_remaining(self, entity_id: str) -> None:
        """Update local remaining duration countdown."""
        chars = self._valve_chars.get(entity_id)
        if chars is None:
            return
        chars["update_timer"] = None
        if chars[CHAR_IN_USE].value != 1:
            return
        remaining = self._remaining_from_local_runtime(entity_id)
        chars[CHAR_REMAINING_DURATION].set_value(remaining)
        self._update_system_state()
        if remaining > 0:
            chars["update_timer"] = async_call_later(
                self.hass,
                1,
                self._make_update_runtime_callback(entity_id),
            )

    def _make_close_runtime_callback(
        self, entity_id: str
    ) -> Callable[[datetime], None]:
        """Create close-timer callback for a specific zone."""

        @callback
        def _close_runtime(_now: datetime) -> None:
            self._async_local_runtime_close(entity_id)

        return _close_runtime

    def _make_update_runtime_callback(
        self, entity_id: str
    ) -> Callable[[datetime], None]:
        """Create remaining-duration update callback for a specific zone."""

        @callback
        def _update_runtime(_now: datetime) -> None:
            self._update_local_remaining(entity_id)

        return _update_runtime

    def _remaining_from_local_runtime(self, entity_id: str) -> int:
        """Return remaining seconds from local runtime tracking."""
        chars = self._valve_chars.get(entity_id)
        if chars is None or (end_time := chars["end_time"]) is None:
            return 0
        return max(int((end_time - dt_util.utcnow()).total_seconds()), 0)

    def _clear_local_runtime(self, entity_id: str) -> None:
        """Cancel local runtime timers for a zone."""
        chars = self._valve_chars.get(entity_id)
        if chars is None:
            return
        if chars["close_timer"] is not None:
            chars["close_timer"]()
            chars["close_timer"] = None
        if chars["update_timer"] is not None:
            chars["update_timer"]()
            chars["update_timer"] = None
        chars["end_time"] = None
