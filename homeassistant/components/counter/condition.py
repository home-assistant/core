"""Provides conditions for counters."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_numerical_condition

DOMAIN = "counter"

CONDITIONS: dict[str, type[Condition]] = {
    "is_value": make_entity_numerical_condition(DOMAIN),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for counters."""
    return CONDITIONS
