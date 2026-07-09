"""Provides triggers for counters."""

from typing import override

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    NotTriggeredReasonReporter,
    Trigger,
)

from . import DOMAIN
from .const import CounterEntityStateAttribute


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

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the new state is valid."""
        return _is_integer_state(state)


class CounterDecrementedTrigger(CounterBaseIntegerTrigger):
    """Trigger for when a counter is decremented."""

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the counter value decreased."""
        return int(from_state.state) > int(to_state.state)


class CounterIncrementedTrigger(CounterBaseIntegerTrigger):
    """Trigger for when a counter is incremented."""

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the counter value increased."""
        return int(from_state.state) < int(to_state.state)


class CounterValueBaseTrigger(EntityTriggerBase):
    """Base trigger for counter value changes."""

    _domain_specs = {DOMAIN: DomainSpec()}


class CounterMaxReachedTrigger(CounterValueBaseTrigger):
    """Trigger for when a counter reaches its maximum value."""

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (
            max_value := state.attributes.get(CounterEntityStateAttribute.MAXIMUM)
        ) is None:
            return False
        return state.state == str(max_value)


class CounterMinReachedTrigger(CounterValueBaseTrigger):
    """Trigger for when a counter reaches its minimum value."""

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (
            min_value := state.attributes.get(CounterEntityStateAttribute.MINIMUM)
        ) is None:
            return False
        return state.state == str(min_value)


class CounterResetTrigger(CounterValueBaseTrigger):
    """Trigger for reset of counter entities."""

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the new state matches the expected state(s)."""
        if (
            init_state := state.attributes.get(CounterEntityStateAttribute.INITIAL)
        ) is None:
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
