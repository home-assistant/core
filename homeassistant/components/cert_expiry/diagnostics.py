"""Diagnostics for the cert_expiry integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import CertExpiryConfigEntry

REDACT_LIST = {CONF_HOST, "host", "name", "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: CertExpiryConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    expiry = coordinator.data.isoformat() if coordinator.data else None
    cert_error = str(coordinator.cert_error) if coordinator.cert_error else None

    # Build entry and coordinator diagnostics.
    entry_diagnostics = {
        "data": entry.data,
        "options": entry.options,
        "title": entry.title,
        "unique_id": entry.unique_id,
    }
    coordinator_diagnostics = {
        "host": coordinator.host,
        "port": coordinator.port,
        "name": coordinator.name,
        "data": expiry,
        "is_cert_valid": coordinator.is_cert_valid,
        "cert_error": cert_error,
        "last_update_success": coordinator.last_update_success,
        "update_interval": str(coordinator.update_interval),
    }

    return {
        "entry": async_redact_data(entry_diagnostics, REDACT_LIST),
        "coordinator": async_redact_data(coordinator_diagnostics, REDACT_LIST),
    }
