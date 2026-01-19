"""Provides triggers for lights."""

from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    EntityNumericalStateAttributeChangedTriggerBase,
    EntityNumericalStateAttributeCrossedThresholdTriggerBase,
    Trigger,
    make_entity_target_state_trigger,
)

from . import ATTR_BRIGHTNESS
from .const import DOMAIN


def _convert_uint8_to_percentage(value: Any) -> float:
    """Convert a uint8 value (0-255) to a percentage (0-100)."""
    value_float = float(value)
    if value_float == 0:
        return 0.0
    return (value_float / 255.0) * 100.0


class BrightnessChangedTrigger(EntityNumericalStateAttributeChangedTriggerBase):
    """Trigger for brightness changed."""

    _domain = DOMAIN
    _attribute = ATTR_BRIGHTNESS

    _convert_attribute = staticmethod(_convert_uint8_to_percentage)


class BrightnessCrossedThresholdTrigger(
    EntityNumericalStateAttributeCrossedThresholdTriggerBase
):
    """Trigger for brightness crossed threshold."""

    _domain = DOMAIN
    _attribute = ATTR_BRIGHTNESS
    _convert_attribute = staticmethod(_convert_uint8_to_percentage)


TRIGGERS: dict[str, type[Trigger]] = {
    "brightness_changed": BrightnessChangedTrigger,
    "brightness_crossed_threshold": BrightnessCrossedThresholdTrigger,
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_target_state_trigger(DOMAIN, STATE_ON),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
