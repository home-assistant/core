"""Provides triggers for counters."""

from homeassistant.const import (
    CONF_MAXIMUM,
    CONF_MINIMUM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
    _is_integer_state,
)

from . import CONF_INITIAL, DOMAIN


class CounterDecrementedTrigger(EntityTriggerBase):
    """Trigger for when a counter is decremented."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return int(from_state.state) > int(to_state.state)

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute is valid."""
        return _is_integer_state(state)


class CounterIncrementedTrigger(EntityTriggerBase):
    """Trigger for when a counter is incremented."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return int(from_state.state) < int(to_state.state)

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute is valid."""
        return _is_integer_state(state)


class CounterMaxReachedTrigger(EntityTriggerBase):
    """Trigger for when a counter reaches its maximum value."""

    _domain_specs = {DOMAIN: DomainSpec()}

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return from_state.state != to_state.state

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (max_value := state.attributes.get(CONF_MAXIMUM)) is None:
            return False
        return state.state == str(max_value)


class CounterMinReachedTrigger(EntityTriggerBase):
    """Trigger for when a counter reaches its minimum value."""

    _domain_specs = {DOMAIN: DomainSpec()}

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return from_state.state != to_state.state

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (min_value := state.attributes.get(CONF_MINIMUM)) is None:
            return False
        return state.state == str(min_value)


class CounterResetTrigger(EntityTriggerBase):
    """Trigger for reset of counter entities."""

    _domain_specs = {DOMAIN: DomainSpec()}

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return from_state.state != to_state.state

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (init_state := state.attributes.get(CONF_INITIAL)) is None:
            return False
        return state.state == str(init_state)


TRIGGERS: dict[str, type[Trigger]] = {
    "decremented": CounterDecrementedTrigger,
    "incremented": CounterIncrementedTrigger,
    "maximum_reached": CounterMaxReachedTrigger,
    "minimum_reached": CounterMinReachedTrigger,
    "reset": CounterResetTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for counters."""
    return TRIGGERS
