"""Provides triggers for selects."""

from homeassistant.components.input_select import DOMAIN as INPUT_SELECT_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)

from .const import DOMAIN


class SelectionChangedTrigger(EntityTriggerBase):
    """Trigger for select entity when its selection changes."""

    _domain_specs = {DOMAIN: DomainSpec(), INPUT_SELECT_DOMAIN: DomainSpec()}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return from_state.state != to_state.state

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state is not invalid."""
        return state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


TRIGGERS: dict[str, type[Trigger]] = {
    "selection_changed": SelectionChangedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for selects."""
    return TRIGGERS
