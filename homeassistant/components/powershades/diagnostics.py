"""Diagnostics support for PowerShades."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import PowerShadesConfigEntry

TO_REDACT = {"ip", "mac", "serial", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PowerShadesConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry_data": async_redact_data(
            {**entry.data, "unique_id": entry.unique_id}, TO_REDACT
        ),
        "coordinator_data": asdict(coordinator.data) if coordinator.data else None,
    }
