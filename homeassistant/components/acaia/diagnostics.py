"""Diagnostics support for Acaia."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import AcaiaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    scale = coordinator.scale

    # collect all data sources
    return {
        "model": scale.model,
        "device_state": (
            asdict(scale.device_state) if scale.device_state is not None else ""
        ),
        "mac": scale.mac,
        "last_disconnect_time": scale.last_disconnect_time,
        "timer": scale.timer,
        "weight": scale.weight,
    }
