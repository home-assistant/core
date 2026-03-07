"""Provides triggers for counters."""

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)

from . import ATTR_STEP, CONF_INITIAL, CONF_MAXIMUM, CONF_MINIMUM, DOMAIN


class CounterStepTrigger(EntityTriggerBase):
    """Base trigger for when a counter value is changed by one step."""

    _domains = {DOMAIN}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if not super().is_valid_transition(from_state, to_state):
            return False

        step_val = int(to_state.attributes[ATTR_STEP])
        from_val = int(from_state.state)
        to_val = int(to_state.state)
        delta = abs(from_val - to_val)

        if delta == step_val:
            return True

        if delta > step_val:
            return False

        max_value = to_state.attributes.get(CONF_MAXIMUM)
        min_value = to_state.attributes.get(CONF_MINIMUM)
        if to_val in (min_value, max_value):
            return True

        return False

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute matches the expected one."""
        try:
            int(state.state)
        except TypeError, ValueError:
            return False
        return True


class CounterDecrementedTrigger(CounterStepTrigger):
    """Trigger for when a counter is decremented."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if not super().is_valid_transition(from_state, to_state):
            return False
        return int(from_state.state) > int(to_state.state)


class CounterIncrementedTrigger(CounterStepTrigger):
    """Trigger for when a counter is incremented."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if not super().is_valid_transition(from_state, to_state):
            return False
        return int(from_state.state) < int(to_state.state)


class CounterMaxReachedTrigger(EntityTriggerBase):
    """Trigger for when a counter reaches its maximum value."""

    _domains = {DOMAIN}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        max_value = state.attributes.get(CONF_MAXIMUM)
        if max_value is None:
            return False
        return state.state == str(max_value)


class CounterResetTrigger(EntityTriggerBase):
    """Trigger for reset of counter entities."""

    _domains = {DOMAIN}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        init_state = state.attributes.get(CONF_INITIAL)
        if init_state is None:
            return False
        return state.state == str(init_state)


TRIGGERS: dict[str, type[Trigger]] = {
    "decremented": CounterDecrementedTrigger,
    "incremented": CounterIncrementedTrigger,
    "maximum_reached": CounterMaxReachedTrigger,
    "reset": CounterResetTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for counters."""
    return TRIGGERS
