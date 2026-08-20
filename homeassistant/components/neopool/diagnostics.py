"""Diagnostics support for the NeoPool integration."""

from typing import Any

from neopool_modbus.decoders import parse_version

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import NeoPoolConfigEntry

TO_REDACT = {"password", "token", "host", "port", "MBF_PAR_SERNUM"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NeoPoolConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a NeoPool config entry."""
    diagnostics: dict[str, Any] = {}

    diagnostics["config_entry"] = async_redact_data(
        {
            "data": dict(entry.data),
            "options": dict(entry.options),
            "title": entry.title,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
            "version": entry.version,
        },
        TO_REDACT | {"title", "unique_id"},
    )

    coordinator = getattr(entry, "runtime_data", None)

    if coordinator is None:
        diagnostics["coordinator"] = {"status": "not loaded"}
        return diagnostics

    # Expose the exception type only; str(exc) would leak host:port.
    last_exception = getattr(coordinator, "last_exception", None)

    diagnostics["coordinator"] = {
        "last_update_success": getattr(coordinator, "last_update_success", None),
        "data": async_redact_data(getattr(coordinator, "data", {}), TO_REDACT),
        "update_interval": str(getattr(coordinator, "update_interval", None)),
        "last_exception": type(last_exception).__name__ if last_exception else None,
        "firmware": parse_version(
            (getattr(coordinator, "data", None) or {}).get("MBF_POWER_MODULE_VERSION")
        ),
    }

    client = getattr(coordinator, "client", None)
    if client and hasattr(client, "connection_stats"):
        diagnostics["connection_stats"] = async_redact_data(
            dict(client.connection_stats), TO_REDACT
        )

    return diagnostics
