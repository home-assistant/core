"""Provides triggers for counters."""

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import EntityTriggerBase, Trigger

from . import CONF_INITIAL, DOMAIN


class CounterResetTrigger(EntityTriggerBase):
    """Trigger for reset of counter entities."""

    _domain = DOMAIN

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""
        init_state = state.attributes.get(CONF_INITIAL)
        return state.state == str(init_state)


TRIGGERS: dict[str, type[Trigger]] = {
    "reset": CounterResetTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for counters."""
    return TRIGGERS
