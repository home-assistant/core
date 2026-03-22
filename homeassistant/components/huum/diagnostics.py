"""Diagnostics support for Huum."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import HuumConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}
TO_REDACT_DATA = {"sauna_name", "payment_end_date"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HuumConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    result: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
            "entry_id": entry.entry_id,
            "version": entry.version,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
        },
    }

    if coordinator.data is None:
        return result

    result["data"] = async_redact_data(coordinator.data.to_dict(), TO_REDACT_DATA)
    return result
