"""Provides conditions for locks."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN, LockState

CONDITIONS: dict[str, type[Condition]] = {
    "is_jammed": make_entity_state_condition(DOMAIN, LockState.JAMMED),
    "is_locked": make_entity_state_condition(DOMAIN, LockState.LOCKED),
    "is_open": make_entity_state_condition(DOMAIN, LockState.OPEN),
    "is_unlocked": make_entity_state_condition(DOMAIN, LockState.UNLOCKED),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for locks."""
    return CONDITIONS
