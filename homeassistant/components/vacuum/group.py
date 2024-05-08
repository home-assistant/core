"""Describe group states."""

from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from homeassistant.components.group import GroupIntegrationRegistry

from .const import DOMAIN, STATE_CLEANING, STATE_ERROR, STATE_RETURNING


@callback
def async_describe_on_off_states(
    hass: HomeAssistant, registry: "GroupIntegrationRegistry"
) -> None:
    """Describe group on off states."""
    registry.on_off_states(
        DOMAIN,
        {
            STATE_ON,
            STATE_CLEANING,
            STATE_RETURNING,
            STATE_ERROR,
        },
        STATE_ON,
        STATE_OFF,
    )
