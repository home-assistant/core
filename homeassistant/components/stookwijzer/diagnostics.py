"""Diagnostics support for Stookwijzer."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    last_updated = None
    if coordinator.client.last_updated:
        last_updated = coordinator.client.last_updated.isoformat()

    return {
        "advice": coordinator.client.advice,
        "air_quality_index": coordinator.client.lki,
        "windspeed_bft": coordinator.client.windspeed_bft,
        "windspeed_ms": coordinator.client.windspeed_ms,
        "forecast_advice": coordinator.client.forecast_advice,
        "last_updated": last_updated,
    }
