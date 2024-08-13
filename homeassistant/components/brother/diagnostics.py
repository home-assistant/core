"""Diagnostics support for Brother."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import BrotherConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BrotherConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        "info": dict(config_entry.data),
        "data": asdict(coordinator.data),
        "model": coordinator.brother.model,
        "firmware": coordinator.brother.firmware,
    }
