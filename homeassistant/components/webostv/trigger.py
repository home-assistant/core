"""LG webOS TV triggers."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

from .triggers.turn_on import LegacyTurnOnTrigger, TurnOnTrigger

TRIGGERS: dict[str, type[Trigger]] = {
    "turn_on": LegacyTurnOnTrigger,
    "turn_on_requested": TurnOnTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for LG webOS TV."""
    return TRIGGERS
