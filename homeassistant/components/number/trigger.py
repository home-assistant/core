"""Provides triggers for number entities."""

from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
)

from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "changed": make_entity_numerical_state_changed_trigger(
        {DOMAIN, INPUT_NUMBER_DOMAIN}
    ),
    "crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {DOMAIN, INPUT_NUMBER_DOMAIN}
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for number entities."""
    return TRIGGERS
