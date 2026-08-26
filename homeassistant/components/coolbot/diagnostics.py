"""Diagnostics for the CoolBot Pro integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import CoolbotConfigEntry, device_is_fresh

TO_REDACT = {
    "password",
    "email",
    "mac_address",
    "unique_id",
    "name",
    "dash_id",
    "device_id",
    "target",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CoolbotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    devices = []
    for device in coordinator.data.values():
        payload = asdict(device)
        # Timestamps are not JSON-serialisable and are more useful as ages anyway.
        payload.pop("last_data_at", None)
        payload["last_disconnect"] = (
            device.last_disconnect.isoformat() if device.last_disconnect else None
        )
        payload["data_age_seconds"] = device.data_age_seconds
        payload["considered_fresh"] = device_is_fresh(device)
        devices.append(async_redact_data(payload, TO_REDACT))

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "device_count": len(devices),
        "devices": devices,
    }
