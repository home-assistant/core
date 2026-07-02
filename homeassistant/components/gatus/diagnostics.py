"""Diagnostics support for Gatus."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import GatusConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GatusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "url": coordinator.url,
        "endpoint_count": len(coordinator.data),
        "endpoints": list(coordinator.data.values()),
    }
