"""Provides conditions for climates."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import (
    Condition,
    make_entity_state_attribute_condition,
    make_entity_state_condition,
)

from .const import ATTR_HVAC_ACTION, DOMAIN, HVACAction, HVACMode

CONDITIONS: dict[str, type[Condition]] = {
    "is_off": make_entity_state_condition(DOMAIN, HVACMode.OFF),
    "is_on": make_entity_state_condition(
        DOMAIN,
        {
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
        },
    ),
    "is_cooling": make_entity_state_attribute_condition(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.COOLING
    ),
    "is_drying": make_entity_state_attribute_condition(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.DRYING
    ),
    "is_heating": make_entity_state_attribute_condition(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.HEATING
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the climate conditions."""
    return CONDITIONS
