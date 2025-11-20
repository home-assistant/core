"""Provides triggers for climates."""

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    Trigger,
    make_conditional_entity_state_trigger,
    make_entity_state_attribute_trigger,
    make_entity_state_trigger,
)

from .const import ATTR_HVAC_ACTION, DOMAIN, HVACAction

COOLING = "cooling"
DEFROSTING = "defrosting"
DRYING = "drying"
FAN = "fan"
HEATING = "heating"
IDLE = "idle"
OFF = "off"
PREHEATING = "preheating"


TRIGGERS: dict[str, type[Trigger]] = {
    "turned_off": make_entity_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_conditional_entity_state_trigger(
        DOMAIN,
        from_states={
            HVACAction.OFF,
        },
        to_states={
            HVACAction.COOLING,
            HVACAction.DEFROSTING,
            HVACAction.DRYING,
            HVACAction.FAN,
            HVACAction.HEATING,
            HVACAction.IDLE,
            HVACAction.PREHEATING,
        },
    ),
    "started_heating": make_entity_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.HEATING
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for climates."""
    return TRIGGERS
