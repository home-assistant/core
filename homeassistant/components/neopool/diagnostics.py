"""Diagnostics support for the NeoPool integration."""

from typing import Any

from neopool_modbus.decoders import parse_version

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import NeoPoolConfigEntry

TO_REDACT = {"password", "token", "host", "port", "name", "MBF_PAR_SERNUM"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NeoPoolConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a NeoPool config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}

    # Expose the exception type only; str(exc) would leak host:port.
    last_exception = coordinator.last_exception

    return {
        "config_entry": async_redact_data(
            {
                "data": dict(entry.data),
                "options": dict(entry.options),
                "title": entry.title,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
                "version": entry.version,
            },
            TO_REDACT | {"title", "unique_id"},
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "data": async_redact_data(data, TO_REDACT),
            "update_interval": str(coordinator.update_interval),
            "last_exception": type(last_exception).__name__ if last_exception else None,
            "firmware": parse_version(data.get("MBF_POWER_MODULE_VERSION")),
        },
        "connection_stats": async_redact_data(
            dict(coordinator.client.connection_stats), TO_REDACT
        ),
    }
