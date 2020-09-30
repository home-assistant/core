"""Describe group states."""


from homeassistant.components.group import GroupIntegrationRegistry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType

from . import STATE_CLEANING, STATE_ERROR, STATE_RETURNING


@callback
def async_describe_on_off_states(
    hass: HomeAssistantType, registry: GroupIntegrationRegistry
) -> None:
    """Describe group on off states."""
    registry.on_off_states(
        {STATE_CLEANING, STATE_ON, STATE_RETURNING, STATE_ERROR}, STATE_OFF
    )
