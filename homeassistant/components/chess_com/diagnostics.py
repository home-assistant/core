"""Diagnostics support for Chess.com."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ChessConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ChessConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "player": asdict(coordinator.data.player),
        "stats": asdict(coordinator.data.stats),
    }
