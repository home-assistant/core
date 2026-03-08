"""Provides triggers for valves."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from .const import DOMAIN, ValveState

TRIGGERS: dict[str, type[Trigger]] = {
    "closed": make_entity_target_state_trigger(DOMAIN, ValveState.CLOSED),
    "opened": make_entity_target_state_trigger(
        DOMAIN, {ValveState.OPEN, ValveState.OPENING}
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for valves."""
    return TRIGGERS
