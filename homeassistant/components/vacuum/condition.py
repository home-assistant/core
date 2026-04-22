"""Provides conditions for vacuum cleaners."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN, VacuumActivity

CONDITIONS: dict[str, type[Condition]] = {
    "is_cleaning": make_entity_state_condition(
        DOMAIN, VacuumActivity.CLEANING, support_duration=True
    ),
    "is_docked": make_entity_state_condition(
        DOMAIN, VacuumActivity.DOCKED, support_duration=True
    ),
    "is_encountering_an_error": make_entity_state_condition(
        DOMAIN, VacuumActivity.ERROR, support_duration=True
    ),
    "is_paused": make_entity_state_condition(
        DOMAIN, VacuumActivity.PAUSED, support_duration=True
    ),
    "is_returning": make_entity_state_condition(
        DOMAIN, VacuumActivity.RETURNING, support_duration=True
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for vacuum cleaners."""
    return CONDITIONS
