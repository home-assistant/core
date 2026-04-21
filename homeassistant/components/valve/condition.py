"""Provides conditions for valves."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from . import ATTR_IS_CLOSED
from .const import DOMAIN

VALVE_DOMAIN_SPECS = {DOMAIN: DomainSpec(value_source=ATTR_IS_CLOSED)}

CONDITIONS: dict[str, type[Condition]] = {
    "is_open": make_entity_state_condition(VALVE_DOMAIN_SPECS, False),
    "is_closed": make_entity_state_condition(VALVE_DOMAIN_SPECS, True),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the valve conditions."""
    return CONDITIONS
