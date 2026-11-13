"""Diagnostics for the cert_expiry integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import CertExpiryConfigEntry

TO_REDACT = {CONF_HOST, "name", "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: CertExpiryConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_diagnostics = entry.as_dict()

    coordinator = getattr(entry, "runtime_data", None)

    coordinator_diagnostics: dict[str, Any] = {
        "host": None,
        "port": None,
        "name": None,
        "expiry_datetime": None,
        "is_cert_valid": None,
        "cert_error": None,
        "last_update_success": None,
    }

    if coordinator is not None:
        expiry = coordinator.data.isoformat() if coordinator.data else None
        cert_error = (
            (
                f"{type(coordinator.cert_error).__module__}."
                f"{type(coordinator.cert_error).__qualname__}"
            )
            if coordinator.cert_error
            else None
        )

        coordinator_diagnostics = {
            "host": coordinator.host,
            "port": coordinator.port,
            "name": coordinator.name,
            "expiry_datetime": expiry,
            "is_cert_valid": coordinator.is_cert_valid,
            "cert_error": cert_error,
            "last_update_success": coordinator.last_update_success,
        }

    return {
        "entry": async_redact_data(entry_diagnostics, TO_REDACT),
        "coordinator": async_redact_data(coordinator_diagnostics, TO_REDACT),
    }
