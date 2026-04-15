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
)

from . import CONF_INITIAL, DOMAIN


def _is_integer_state(state: State) -> bool:
    """Return True if the state's value can be interpreted as an integer."""
    try:
        int(state.state)
    except TypeError, ValueError:
        return False
    return True


class CounterBaseIntegerTrigger(EntityTriggerBase):
    """Base trigger for valid counter integer states."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state is valid."""
        return _is_integer_state(state)


class CounterDecrementedTrigger(CounterBaseIntegerTrigger):
    """Trigger for when a counter is decremented."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return int(from_state.state) > int(to_state.state)


class CounterIncrementedTrigger(CounterBaseIntegerTrigger):
    """Trigger for when a counter is incremented."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return int(from_state.state) < int(to_state.state)


class CounterValueBaseTrigger(EntityTriggerBase):
    """Base trigger for counter value changes."""

    _domain_specs = {DOMAIN: DomainSpec()}

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return from_state.state != to_state.state


class CounterMaxReachedTrigger(CounterValueBaseTrigger):
    """Trigger for when a counter reaches its maximum value."""

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (max_value := state.attributes.get(CONF_MAXIMUM)) is None:
            return False
        return state.state == str(max_value)


class CounterMinReachedTrigger(CounterValueBaseTrigger):
    """Trigger for when a counter reaches its minimum value."""

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (min_value := state.attributes.get(CONF_MINIMUM)) is None:
            return False
        return state.state == str(min_value)


class CounterResetTrigger(CounterValueBaseTrigger):
    """Trigger for reset of counter entities."""

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
