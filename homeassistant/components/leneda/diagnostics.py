"""Diagnostics support for Leneda."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
    return {
        "data": coordinator.data,
    }
