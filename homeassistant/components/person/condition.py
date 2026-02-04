"""Provides conditions for persons."""

from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN

CONDITIONS: dict[str, type[Condition]] = {
    "is_home": make_entity_state_condition(DOMAIN, STATE_HOME),
    "is_not_home": make_entity_state_condition(DOMAIN, STATE_NOT_HOME),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for persons."""
    return CONDITIONS
