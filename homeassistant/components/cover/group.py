"""Describe group states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.components.group import GroupIntegrationRegistry


@callback
def async_describe_on_off_states(
    hass: HomeAssistant, registry: GroupIntegrationRegistry
) -> None:
    """Describe group on off states."""
    # On means open, Off means closed
    registry.on_off_states(DOMAIN, {STATE_OPEN}, STATE_OPEN, STATE_CLOSED)
