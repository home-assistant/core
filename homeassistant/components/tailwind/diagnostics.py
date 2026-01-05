"""Diagnostics platform for Tailwind."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import TailwindConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TailwindConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return entry.runtime_data.data.to_dict()
