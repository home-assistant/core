"""Provides triggers for climates."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    Trigger,
    make_conditional_entity_state_trigger,
    make_entity_state_attribute_trigger,
    make_entity_state_trigger,
)

from .const import ATTR_HVAC_ACTION, DOMAIN, HVACAction, HVACMode

TRIGGERS: dict[str, type[Trigger]] = {
    "started_cooling": make_entity_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.COOLING
    ),
    "started_drying": make_entity_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.DRYING
    ),
    "turned_off": make_entity_state_trigger(DOMAIN, HVACMode.OFF),
    "turned_on": make_conditional_entity_state_trigger(
        DOMAIN,
        from_states={
            HVACMode.OFF,
        },
        to_states={
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
        },
    ),
    "started_heating": make_entity_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.HEATING
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for climates."""
    return TRIGGERS
