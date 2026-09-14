"""Provides conditions for timers."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from . import DOMAIN, STATUS_ACTIVE, STATUS_IDLE, STATUS_PAUSED

CONDITIONS: dict[str, type[Condition]] = {
    "is_active": make_entity_state_condition(DOMAIN, STATUS_ACTIVE),
    "is_paused": make_entity_state_condition(DOMAIN, STATUS_PAUSED),
    "is_idle": make_entity_state_condition(DOMAIN, STATUS_IDLE),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the timer conditions."""
    return CONDITIONS
