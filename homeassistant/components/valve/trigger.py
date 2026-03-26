"""Provides triggers for valves."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import EntityTriggerBase, Trigger

from . import ATTR_IS_CLOSED, DOMAIN


class ValveTriggerBase(EntityTriggerBase):
    """Base trigger for valve state changes."""

    _domain_specs = {DOMAIN: DomainSpec()}

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the transition is valid for a valve state change."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        if (from_value := from_state.attributes.get(ATTR_IS_CLOSED)) is None or (
            to_value := to_state.attributes.get(ATTR_IS_CLOSED)
        ) is None:
            return False

        return bool(from_value) is not bool(to_value)


class ValveClosedTrigger(ValveTriggerBase):
    """Trigger for valve closed state changes."""

    def is_valid_state(self, state: State) -> bool:
        """Check if the state matches the target valve state."""
        return state.attributes.get(ATTR_IS_CLOSED) is True


class ValveOpenedTrigger(ValveTriggerBase):
    """Trigger for valve opened state changes."""

    def is_valid_state(self, state: State) -> bool:
        """Check if the state matches the target valve state."""
        return state.attributes.get(ATTR_IS_CLOSED) is False


TRIGGERS: dict[str, type[Trigger]] = {
    "closed": ValveClosedTrigger,
    "opened": ValveOpenedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for valves."""
    return TRIGGERS
