"""Provides triggers for switch platform."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "turned_on": make_entity_target_state_trigger(DOMAIN, STATE_ON),
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for switch platform."""
    return TRIGGERS
