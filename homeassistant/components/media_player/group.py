"""Describe group states."""


from homeassistant.components.group import GroupIntegrationRegistry
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant, callback


@callback
def async_describe_on_off_states(
    hass: HomeAssistant, registry: GroupIntegrationRegistry
) -> None:
    """Describe group on off states."""
    registry.on_off_states(
        {STATE_ON, STATE_PAUSED, STATE_PLAYING, STATE_IDLE}, STATE_OFF
    )
