"""Provides triggers for lights."""

from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import NumericalDomainSpec
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
    make_entity_target_state_trigger,
)

from . import ATTR_BRIGHTNESS
from .const import DOMAIN


def _convert_uint8_to_percentage(value: Any) -> float:
    """Convert a uint8 value (0-255) to a percentage (0-100)."""
    return (float(value) / 255.0) * 100.0


BRIGHTNESS_DOMAIN_SPECS = {
    DOMAIN: NumericalDomainSpec(
        value_source=ATTR_BRIGHTNESS,
        value_converter=_convert_uint8_to_percentage,
    ),
}

TRIGGERS: dict[str, type[Trigger]] = {
    "brightness_changed": make_entity_numerical_state_changed_trigger(
        BRIGHTNESS_DOMAIN_SPECS
    ),
    "brightness_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        BRIGHTNESS_DOMAIN_SPECS
    ),
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_target_state_trigger(DOMAIN, STATE_ON),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
