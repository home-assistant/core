"""Describe group states."""


from homeassistant.components.group import GroupIntegrationRegistry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_TRIGGERED,
    STATE_OFF,
)
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType


@callback
def async_describe_on_off_states(
    hass: HomeAssistantType, registry: GroupIntegrationRegistry
) -> None:
    """Describe group on off states."""
    registry.on_off_states(
        {
            STATE_ALARM_ARMED_AWAY,
            STATE_ALARM_ARMED_CUSTOM_BYPASS,
            STATE_ALARM_ARMED_HOME,
            STATE_ALARM_ARMED_NIGHT,
            STATE_ALARM_TRIGGERED,
        },
        STATE_OFF,
    )
