"""Provides triggers for buttons."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)

from . import DOMAIN


class ButtonPressedTrigger(EntityTriggerBase):
    """Trigger for button entity presses."""

    _domain = DOMAIN
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and different from the current state."""

        # UNKNOWN is a valid from_state, otherwise the first time the button is pressed
        # would not trigger
        if from_state.state == STATE_UNAVAILABLE:
            return False

        return from_state.state != to_state.state

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state is not invalid."""
        return state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


TRIGGERS: dict[str, type[Trigger]] = {
    "pressed": ButtonPressedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for buttons."""
    return TRIGGERS
