"""Provides conditions for lights."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN

CONDITIONS: dict[str, type[Condition]] = {
    "is_off": make_entity_state_condition(DOMAIN, STATE_OFF),
    "is_on": make_entity_state_condition(DOMAIN, STATE_ON),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the light conditions."""
    return CONDITIONS
