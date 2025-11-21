"""Provides triggers for texts."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)

from .const import DOMAIN


class TextChangedTrigger(EntityTriggerBase):
    """Trigger for text entity when its content changes."""

    _domain = DOMAIN
    _schema = ENTITY_STATE_TRIGGER_SCHEMA

    def is_from_state(self, from_state: State, to_state: State) -> bool:
        """Check if the state matches the origin state."""
        return from_state.state != to_state.state

    def is_to_state(self, state: State) -> bool:
        """Check if the state matches the target state."""
        return state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": TextChangedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for texts."""
    return TRIGGERS
