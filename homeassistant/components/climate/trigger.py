"""Provides triggers for climates."""

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_state_attribute_trigger,
    make_entity_state_trigger,
)

from .const import ATTR_HVAC_ACTION, DOMAIN, HVACAction

TRIGGERS: dict[str, type[Trigger]] = {
    "turned_off": make_entity_state_trigger(DOMAIN, STATE_OFF),
    "started_heating": make_entity_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.HEATING
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for climates."""
    return TRIGGERS
