"""Provides triggers for counters."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import EntityTriggerBase, Trigger

from . import ATTR_STEP, CONF_INITIAL, CONF_MAXIMUM, DOMAIN


class CounterStepTrigger(EntityTriggerBase):
    """Base trigger for when a counter value is changed by one step."""

    _domains = {DOMAIN}

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if not super().is_valid_transition(from_state, to_state):
            return False
        step = to_state.attributes[ATTR_STEP]
        if TYPE_CHECKING:
            assert isinstance(step, int)
        return abs(int(from_state.state) - int(to_state.state)) == step

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

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        max_value = state.attributes.get(CONF_MAXIMUM)
        if max_value is None:
            return False
        return state.state == str(max_value)


class CounterResetTrigger(EntityTriggerBase):
    """Trigger for reset of counter entities."""

    _domains = {DOMAIN}

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        init_state = state.attributes.get(CONF_INITIAL)
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
