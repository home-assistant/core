"""Provides triggers for device_trackers."""

from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_origin_state_trigger,
    make_entity_target_state_trigger,
)

from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "entered_home": make_entity_target_state_trigger(DOMAIN, STATE_HOME),
    "left_home": make_entity_origin_state_trigger(DOMAIN, from_state=STATE_HOME),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for device trackers."""
    return TRIGGERS
