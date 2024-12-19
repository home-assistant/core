"""Diagnostics support for Bring."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant

from . import BringConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BringConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "user_settings": config_entry.runtime_data.user_settings,
        "lists": config_entry.runtime_data.lists,
        "list_items": config_entry.runtime_data.data,
    }
