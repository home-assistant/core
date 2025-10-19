"""Diagnostics support for Paperless-ngx."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import PaperlessConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "pngx_version": entry.runtime_data.status.api.host_version,
        "data": {
            "statistics": asdict(entry.runtime_data.statistics.data),
            "status": asdict(entry.runtime_data.status.data),
        },
    }
