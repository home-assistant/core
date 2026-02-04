"""Provides conditions for lawn mowers."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN, LawnMowerActivity

CONDITIONS: dict[str, type[Condition]] = {
    "is_docked": make_entity_state_condition(DOMAIN, LawnMowerActivity.DOCKED),
    "is_encountering_an_error": make_entity_state_condition(
        DOMAIN, LawnMowerActivity.ERROR
    ),
    "is_mowing": make_entity_state_condition(DOMAIN, LawnMowerActivity.MOWING),
    "is_paused": make_entity_state_condition(DOMAIN, LawnMowerActivity.PAUSED),
    "is_returning": make_entity_state_condition(DOMAIN, LawnMowerActivity.RETURNING),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for lawn mowers."""
    return CONDITIONS
