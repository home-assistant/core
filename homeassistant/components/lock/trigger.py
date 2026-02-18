"""Provides triggers for locks."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from .const import DOMAIN, LockState

TRIGGERS: dict[str, type[Trigger]] = {
    "jammed": make_entity_target_state_trigger(DOMAIN, LockState.JAMMED),
    "locked": make_entity_target_state_trigger(DOMAIN, LockState.LOCKED),
    "opened": make_entity_target_state_trigger(DOMAIN, LockState.OPEN),
    "unlocked": make_entity_target_state_trigger(DOMAIN, LockState.UNLOCKED),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for locks."""
    return TRIGGERS
