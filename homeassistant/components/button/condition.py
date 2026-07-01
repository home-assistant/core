"""Provides conditions for button."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_datetime_condition

from .const import DOMAIN

CONDITIONS: dict[str, type[Condition]] = {
    "was_pressed": make_entity_datetime_condition(DOMAIN),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for button."""
    return CONDITIONS
