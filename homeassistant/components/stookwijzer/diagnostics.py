"""Diagnostics support for Stookwijzer."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import StookwijzerConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StookwijzerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client = entry.runtime_data.client
    return {
        "advice": client.advice,
        "air_quality_index": client.lki,
        "windspeed_ms": client.windspeed_ms,
        "forecast": await client.async_get_forecast(),
    }
