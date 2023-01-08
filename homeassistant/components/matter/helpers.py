"""Provide integration helpers that are aware of the matter integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from .adapter import MatterAdapter


@dataclass
class MatterEntryData:
    """Hold Matter data for the config entry."""

    adapter: MatterAdapter
    listen_task: asyncio.Task


@callback
def get_matter(hass: HomeAssistant) -> MatterAdapter:
    """Return MatterAdapter instance."""
    # NOTE: This assumes only one Matter connection/fabric can exist.
    # Shall we support connecting to multiple servers in the client or by config entries?
    # In case of the config entry we need to fix this.
    matter_entry_data: MatterEntryData = next(iter(hass.data[DOMAIN].values()))
    return matter_entry_data.adapter
