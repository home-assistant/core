"""Provides triggers for counters."""

from homeassistant.const import CONF_MAXIMUM, CONF_MINIMUM
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)

from . import CONF_INITIAL, DOMAIN


class CounterDecrementedTrigger(EntityTriggerBase):
    """Trigger for when a counter is decremented."""

    _domains = {DOMAIN}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if not super().is_valid_transition(from_state, to_state):
            return False
        return int(from_state.state) > int(to_state.state)

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute is valid."""
        try:
            int(state.state)
        except TypeError, ValueError:
            return False
        return True


class CounterIncrementedTrigger(EntityTriggerBase):
    """Trigger for when a counter is incremented."""

    _domains = {DOMAIN}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if not super().is_valid_transition(from_state, to_state):
            return False
        return int(from_state.state) < int(to_state.state)

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute is valid."""
        try:
            int(state.state)
        except TypeError, ValueError:
            return False
        return True


class CounterMaxReachedTrigger(EntityTriggerBase):
    """Trigger for when a counter reaches its maximum value."""

    _domains = {DOMAIN}

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (max_value := state.attributes.get(CONF_MAXIMUM)) is None:
            return False
        return state.state == str(max_value)


class CounterMinReachedTrigger(EntityTriggerBase):
    """Trigger for when a counter reaches its minimum value."""

    _domains = {DOMAIN}

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (min_value := state.attributes.get(CONF_MINIMUM)) is None:
            return False
        return state.state == str(min_value)


class CounterResetTrigger(EntityTriggerBase):
    """Trigger for reset of counter entities."""

    _domains = {DOMAIN}

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
