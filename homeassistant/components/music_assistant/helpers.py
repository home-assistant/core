"""Provide integration helpers that are aware of the mass integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient


@dataclass
class MassEntryData:
    """Hold Mass data for the config entry."""

    mass: MusicAssistantClient
    listen_task: asyncio.Task


@callback
def get_mass(
    hass: HomeAssistant, entry_id: str | None = None
) -> MusicAssistantClient | None:
    """Return MusicAssistantClient instance."""
    if DOMAIN not in hass.data:
        return None
    for key, value in hass.data[DOMAIN].items():
        if entry_id is not None and entry_id != key:
            continue
        mass_entry_data: MassEntryData = value
        return mass_entry_data.mass
    return None
