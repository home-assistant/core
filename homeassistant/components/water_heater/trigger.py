"""Provides triggers for water heaters."""

from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_numerical_state_attribute_changed_trigger,
    make_entity_numerical_state_attribute_crossed_threshold_trigger,
    make_entity_origin_state_trigger,
    make_entity_target_state_trigger,
)

from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "target_temperature_changed": make_entity_numerical_state_attribute_changed_trigger(
        DOMAIN, ATTR_TEMPERATURE
    ),
    "target_temperature_crossed_threshold": make_entity_numerical_state_attribute_crossed_threshold_trigger(
        DOMAIN, ATTR_TEMPERATURE
    ),
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_origin_state_trigger(DOMAIN, from_state=STATE_OFF),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for water heaters."""
    return TRIGGERS
