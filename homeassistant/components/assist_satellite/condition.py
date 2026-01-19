"""Provides conditions for assist satellites."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN
from .entity import AssistSatelliteState

CONDITIONS: dict[str, type[Condition]] = {
    "is_idle": make_entity_state_condition(DOMAIN, AssistSatelliteState.IDLE),
    "is_listening": make_entity_state_condition(DOMAIN, AssistSatelliteState.LISTENING),
    "is_processing": make_entity_state_condition(
        DOMAIN, AssistSatelliteState.PROCESSING
    ),
    "is_responding": make_entity_state_condition(
        DOMAIN, AssistSatelliteState.RESPONDING
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the assist satellite conditions."""
    return CONDITIONS
