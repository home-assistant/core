"""Provides triggers for schedules."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    EntityTransitionTriggerBase,
    Trigger,
    make_entity_target_state_trigger,
)

from .const import ATTR_NEXT_EVENT, DOMAIN


class ScheduleBackToBackTrigger(EntityTransitionTriggerBase):
    """Trigger for back-to-back schedule blocks."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _from_states = {STATE_OFF, STATE_ON}
    _to_states = {STATE_ON}

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the origin matches and the next event changed."""
        from_next_event = from_state.attributes.get(ATTR_NEXT_EVENT)
        to_next_event = to_state.attributes.get(ATTR_NEXT_EVENT)

        return (
            from_state.state in self._from_states and from_next_event != to_next_event
        )


TRIGGERS: dict[str, type[Trigger]] = {
    "turned_on": ScheduleBackToBackTrigger,
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for schedules."""
    return TRIGGERS
