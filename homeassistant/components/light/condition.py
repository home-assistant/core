"""Provides conditions for lights."""

from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    EntityNumericalConditionBase,
    make_entity_state_condition,
)

from . import ATTR_BRIGHTNESS
from .const import DOMAIN

BRIGHTNESS_DOMAIN_SPECS = {
    DOMAIN: DomainSpec(value_source=ATTR_BRIGHTNESS),
}


class BrightnessCondition(EntityNumericalConditionBase):
    """Condition for light brightness with uint8 to percentage conversion."""

    _domain_specs = BRIGHTNESS_DOMAIN_SPECS
    _valid_unit = "%"

    def _get_tracked_value(self, entity_state: State) -> Any:
        """Get the brightness value converted from uint8 (0-255) to percentage (0-100)."""
        raw = super()._get_tracked_value(entity_state)
        if raw is None:
            return None
        try:
            return (float(raw) / 255.0) * 100.0
        except TypeError, ValueError:
            return None


CONDITIONS: dict[str, type[Condition]] = {
    "is_brightness": BrightnessCondition,
    "is_off": make_entity_state_condition(DOMAIN, STATE_OFF),
    "is_on": make_entity_state_condition(DOMAIN, STATE_ON),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the light conditions."""
    return CONDITIONS
