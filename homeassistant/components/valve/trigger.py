"""Provides triggers for valves."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import Trigger, make_entity_transition_trigger

from . import ATTR_IS_CLOSED, DOMAIN

VALVE_DOMAIN_SPECS = {DOMAIN: DomainSpec(value_source=ATTR_IS_CLOSED)}


TRIGGERS: dict[str, type[Trigger]] = {
    "closed": make_entity_transition_trigger(
        VALVE_DOMAIN_SPECS, from_states={False}, to_states={True}
    ),
    "opened": make_entity_transition_trigger(
        VALVE_DOMAIN_SPECS, from_states={True}, to_states={False}
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for valves."""
    return TRIGGERS
