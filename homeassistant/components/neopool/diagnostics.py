"""Diagnostics support for the NeoPool integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NeoPoolConfigEntry

TO_REDACT = {"password", "token", "host", "port"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NeoPoolConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a NeoPool config entry."""
    diagnostics: dict[str, Any] = {}

    diagnostics["config_entry"] = {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "title": entry.title,
        "entry_id": entry.entry_id,
        "unique_id": entry.unique_id,
        "version": entry.version,
    }

    coordinator = getattr(entry, "runtime_data", None)

    if coordinator is None:
        diagnostics["coordinator"] = {"status": "not loaded"}
        return diagnostics

    diagnostics["coordinator"] = {
        "last_update_success": getattr(coordinator, "last_update_success", None),
        "last_update_time": str(getattr(coordinator, "last_update_time", None)),
        "data": getattr(coordinator, "data", {}),
        "update_interval": str(getattr(coordinator, "update_interval", None)),
        "last_exception": str(getattr(coordinator, "last_exception", "")),
        "firmware": getattr(coordinator, "firmware", None),
        "model": getattr(coordinator, "model", None),
    }

    client = getattr(coordinator, "client", None)
    if client and hasattr(client, "connection_stats"):
        diagnostics["connection_stats"] = async_redact_data(
            dict(client.connection_stats), TO_REDACT
        )

    return diagnostics
