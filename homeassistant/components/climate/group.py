"""Describe group states."""

from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, HVACMode

if TYPE_CHECKING:
    from homeassistant.components.group import GroupIntegrationRegistry


@callback
def async_describe_on_off_states(
    hass: HomeAssistant, registry: "GroupIntegrationRegistry"
) -> None:
    """Describe group on off states."""
    registry.on_off_states(
        DOMAIN,
        {
            STATE_ON,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.AUTO,
            HVACMode.FAN_ONLY,
        },
        STATE_ON,
        STATE_OFF,
    )
