"""Diagnostics support for mijn.ista.nl."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import MijnIstaConfigEntry

_REDACT = {"password", "JWT", "username"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MijnIstaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry, with credentials redacted."""
    coordinator = entry.runtime_data

    properties: dict[str, Any] = {}
    for cuid, c in (coordinator.data or {}).items():
        properties[cuid[:8] + "…"] = {
            "location": f"{c.zip_code} {c.city}",
            "services": [
                {"id": s.id, "description": s.description, "unit": s.unit}
                for s in c.services
            ],
            "monthly_entries": len(c.monthly),
            "annual_service_ids": list(c.annual.keys()),
            "building_average_service_ids": list(c.building_averages.keys()),
            "cur_period_temp": c.cur_period_temp,
            "prev_period_temp": c.prev_period_temp,
        }

    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "properties": properties,
            },
        },
        _REDACT,
    )
