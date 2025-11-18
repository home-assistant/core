"""Provides triggers for alarm control panels."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_state_trigger

from .const import DOMAIN, AlarmControlPanelState

TRIGGERS: dict[str, type[Trigger]] = {
    "disarmed": make_entity_state_trigger(DOMAIN, AlarmControlPanelState.DISARMED),
    "triggered": make_entity_state_trigger(DOMAIN, AlarmControlPanelState.TRIGGERED),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for alarm control panels."""
    return TRIGGERS
