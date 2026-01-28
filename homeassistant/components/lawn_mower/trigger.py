"""Provides triggers for lawn mowers."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from .const import DOMAIN, LawnMowerActivity

TRIGGERS: dict[str, type[Trigger]] = {
    "docked": make_entity_target_state_trigger(DOMAIN, LawnMowerActivity.DOCKED),
    "errored": make_entity_target_state_trigger(DOMAIN, LawnMowerActivity.ERROR),
    "paused_mowing": make_entity_target_state_trigger(DOMAIN, LawnMowerActivity.PAUSED),
    "started_mowing": make_entity_target_state_trigger(
        DOMAIN, LawnMowerActivity.MOWING
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lawn mowers."""
    return TRIGGERS
