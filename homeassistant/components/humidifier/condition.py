"""Provides conditions for humidifiers."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import (
    Condition,
    make_entity_state_attribute_condition,
    make_entity_state_condition,
)

from .const import ATTR_ACTION, DOMAIN, HumidifierAction

CONDITIONS: dict[str, type[Condition]] = {
    "is_off": make_entity_state_condition(DOMAIN, STATE_OFF),
    "is_on": make_entity_state_condition(DOMAIN, STATE_ON),
    "is_drying": make_entity_state_attribute_condition(
        DOMAIN, ATTR_ACTION, HumidifierAction.DRYING
    ),
    "is_humidifying": make_entity_state_attribute_condition(
        DOMAIN, ATTR_ACTION, HumidifierAction.HUMIDIFYING
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the humidifier conditions."""
    return CONDITIONS
