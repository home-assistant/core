"""Provides triggers for valves."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from . import ATTR_IS_CLOSED, DOMAIN

VALVE_DOMAIN_SPECS = {DOMAIN: DomainSpec(value_source=ATTR_IS_CLOSED)}


TRIGGERS: dict[str, type[Trigger]] = {
    "closed": make_entity_target_state_trigger(VALVE_DOMAIN_SPECS, True),
    "opened": make_entity_target_state_trigger(VALVE_DOMAIN_SPECS, False),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for valves."""
    return TRIGGERS
