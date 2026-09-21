"""Diagnostics for the cert_expiry integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import CertExpiryConfigEntry

# issuer_common_name is redacted alongside common_name because a self-signed
# certificate's issuer CN is its subject CN. cert_error is redacted because
# verify_cert() embeds the configured hostname in its message. fingerprint and
# serial_number are left unredacted: they identify the certificate, not the
# host, and are useful for cross-checking against other tools.
TO_REDACT = {
    CONF_HOST,
    "name",
    "title",
    "unique_id",
    "common_name",
    "issuer_common_name",
    "cert_error",
}


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
        "last_update_success": None,
        "data": None,
    }

    if coordinator is not None:
        data = coordinator.data
        coordinator_diagnostics = {
            "host": coordinator.host,
            "port": coordinator.port,
            "name": coordinator.name,
            "last_update_success": coordinator.last_update_success,
            "data": None if data is None else asdict(data),
        }

    return {
        "entry": async_redact_data(entry_diagnostics, TO_REDACT),
        "coordinator": async_redact_data(coordinator_diagnostics, TO_REDACT),
    }
