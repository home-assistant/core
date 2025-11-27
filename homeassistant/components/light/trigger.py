"""Provides triggers for lights."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_state_trigger

from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "turned_off": make_entity_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_state_trigger(DOMAIN, STATE_ON),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
