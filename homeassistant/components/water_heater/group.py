"""Describe group states."""

from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from homeassistant.components.group import GroupIntegrationRegistry

from .const import (
    DOMAIN,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)


@callback
def async_describe_on_off_states(
    hass: HomeAssistant, registry: "GroupIntegrationRegistry"
) -> None:
    """Describe group on off states."""
    registry.on_off_states(
        DOMAIN,
        {
            STATE_ON,
            STATE_ECO,
            STATE_ELECTRIC,
            STATE_PERFORMANCE,
            STATE_HIGH_DEMAND,
            STATE_HEAT_PUMP,
            STATE_GAS,
        },
        STATE_ON,
        STATE_OFF,
    )
