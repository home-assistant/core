"""Diagnostics support for EnergyID."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import EnergyIDConfigEntry
from .const import CONF_PROVISIONING_KEY, CONF_PROVISIONING_SECRET, DATA_CLIENT, DOMAIN

TO_REDACT_CONFIG = {
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
}
TO_REDACT_CLIENT_ATTRIBUTES = {
    "headers",
    "provisioning_key",
    "provisioning_secret",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: EnergyIDConfigEntry,  # Use the typed ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag_data: dict[str, Any] = {}

    redacted_entry_data = {
        k: ("***REDACTED***" if k in TO_REDACT_CONFIG else v)
        for k, v in entry.data.items()
    }
    diag_data["config_entry_data"] = redacted_entry_data
    diag_data["config_entry_options"] = dict(entry.options)
    diag_data["config_entry_title"] = entry.title
    diag_data["config_entry_id"] = entry.entry_id
    diag_data["config_entry_unique_id"] = entry.unique_id

    client_info: dict[str, Any] = {}
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        integration_data = hass.data[DOMAIN][entry.entry_id]
        client = integration_data.get(DATA_CLIENT)
        if client:
            client_info["is_claimed"] = client.is_claimed
            client_info["webhook_url"] = client.webhook_url
            client_info["record_number"] = client.recordNumber
            client_info["record_name"] = client.recordName
            client_info["webhook_policy"] = client.webhook_policy
            client_info["device_id_for_eid"] = client.device_id
            client_info["device_name_for_eid"] = client.device_name
            client_info["last_sync_time"] = (
                client.last_sync_time.isoformat() if client.last_sync_time else None
            )
            client_info["auth_valid_until"] = (
                client.auth_valid_until.isoformat() if client.auth_valid_until else None
            )
            client_info["is_client_active"] = (
                client.is_auto_sync_active()
                if hasattr(client, "is_auto_sync_active")
                else False
            )
        else:
            client_info["status"] = "Client not found in hass.data"
    else:
        client_info["status"] = "Integration data not found in hass.data"

    diag_data["client_information"] = client_info

    return diag_data
