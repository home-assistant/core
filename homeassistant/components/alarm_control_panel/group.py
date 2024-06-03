"""Describe group states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_TRIGGERED,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.components.group import GroupIntegrationRegistry


@callback
def async_describe_on_off_states(
    hass: HomeAssistant, registry: GroupIntegrationRegistry
) -> None:
    """Describe group on off states."""
    registry.on_off_states(
        DOMAIN,
        {
            STATE_ON,
            STATE_ALARM_ARMED_AWAY,
            STATE_ALARM_ARMED_CUSTOM_BYPASS,
            STATE_ALARM_ARMED_HOME,
            STATE_ALARM_ARMED_NIGHT,
            STATE_ALARM_ARMED_VACATION,
            STATE_ALARM_TRIGGERED,
        },
        STATE_ON,
        STATE_OFF,
    )
