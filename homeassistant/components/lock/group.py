"""Describe group states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import (
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
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
            STATE_LOCKING,
            STATE_OPEN,
            STATE_OPENING,
            STATE_UNLOCKED,
            STATE_UNLOCKING,
        },
        STATE_UNLOCKED,
        STATE_LOCKED,
    )
