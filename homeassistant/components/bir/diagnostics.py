"""Diagnostics support for BIR."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import BirConfigEntry

TO_REDACT = {"property_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BirConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator_data": {
            waste_type: {
                "date": str(pickup["date"]),
                "days_until": pickup["days_until"],
            }
            for waste_type, pickup in entry.runtime_data.data.items()
        },
    }
