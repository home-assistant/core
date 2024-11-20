"""Sensors flor for Powerfox integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(hass: HomeAssistant, entry: PowerfoxConfigFlow, async_add_entities: AddEntitiesCallback,) -> None:
    """Set up Powerfox sensors based on a config entry."""
    pass
    