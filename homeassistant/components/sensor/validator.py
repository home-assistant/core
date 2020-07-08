"""Validate the sensor integration."""
from typing import cast

from homeassistant.components import validator
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State

from . import DOMAIN


async def async_validate_entities(
    hass: HomeAssistant, report: validator.Report
) -> None:
    """Validate sensor entities."""
    for entity_id in hass.states.async_entity_ids(DOMAIN):
        state = cast(State, hass.states.get(entity_id))
        report.async_validate_base_attributes(state)
        report.async_validate_supported_features(state, {})  # no supported features

        if ATTR_UNIT_OF_MEASUREMENT not in state.attributes or state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            continue

        try:
            float(state.state)
        except ValueError:
            report.async_add_warning(
                entity_id,
                f"State with a unit of measurement should be numeric. Got '{state.state}'",
            )
