"""Provides triggers for vacuum cleaners."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from .const import DOMAIN, VacuumActivity

TRIGGERS: dict[str, type[Trigger]] = {
    "docked": make_entity_target_state_trigger(DOMAIN, VacuumActivity.DOCKED),
    "errored": make_entity_target_state_trigger(DOMAIN, VacuumActivity.ERROR),
    "paused_cleaning": make_entity_target_state_trigger(DOMAIN, VacuumActivity.PAUSED),
    "started_cleaning": make_entity_target_state_trigger(
        DOMAIN, VacuumActivity.CLEANING
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for vacuum cleaners."""
    return TRIGGERS
