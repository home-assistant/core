"""Diagnostics support for Indevolt."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import IndevoltConfigEntry

TO_REDACT = {"sn"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IndevoltConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data

    return async_redact_data(
        {
            "entry": async_redact_data(entry.data, TO_REDACT),
            "data": data,
        },
        TO_REDACT,
    )
