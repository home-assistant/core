"""Provides triggers for lights."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_numerical_state_attribute_changed_trigger,
    make_entity_numerical_state_attribute_crossed_threshold_trigger,
    make_entity_target_state_trigger,
)

from . import ATTR_BRIGHTNESS
from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "brightness_changed": make_entity_numerical_state_attribute_changed_trigger(
        DOMAIN, ATTR_BRIGHTNESS
    ),
    "brightness_crossed_threshold": make_entity_numerical_state_attribute_crossed_threshold_trigger(
        DOMAIN, ATTR_BRIGHTNESS
    ),
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_target_state_trigger(DOMAIN, STATE_ON),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
