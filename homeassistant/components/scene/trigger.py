"""Provides triggers for scenes."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)

from . import DOMAIN


class SceneActivatedTrigger(EntityTriggerBase):
    """Trigger for scene entity activations."""

    _domain = DOMAIN
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and different from the current state."""

        # UNKNOWN is a valid from_state, otherwise the first time the scene is activated
        # it would not trigger
        if from_state.state == STATE_UNAVAILABLE:
            return False

        return from_state.state != to_state.state

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state is not invalid."""
        return state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


TRIGGERS: dict[str, type[Trigger]] = {
    "activated": SceneActivatedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for scenes."""
    return TRIGGERS
