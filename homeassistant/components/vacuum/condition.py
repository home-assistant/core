"""Provides conditions for vacuum cleaners."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN, VacuumActivity

CONDITIONS: dict[str, type[Condition]] = {
    "is_cleaning": make_entity_state_condition(DOMAIN, VacuumActivity.CLEANING),
    "is_docked": make_entity_state_condition(DOMAIN, VacuumActivity.DOCKED),
    "is_encountering_an_error": make_entity_state_condition(
        DOMAIN, VacuumActivity.ERROR
    ),
    "is_paused": make_entity_state_condition(DOMAIN, VacuumActivity.PAUSED),
    "is_returning": make_entity_state_condition(DOMAIN, VacuumActivity.RETURNING),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for vacuum cleaners."""
    return CONDITIONS
