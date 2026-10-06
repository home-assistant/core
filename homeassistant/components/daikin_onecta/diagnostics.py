"""Diagnostics support for Daikin Onecta."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import DaikinOnectaConfigEntry

TO_REDACT = {
    "access_token",
    "embeddedId",
    "embedded_id",
    "entry_id",
    "id",
    "ipAddress",
    "macAddress",
    "mac_address",
    "name",
    "refresh_token",
    "serialNumber",
    "serial_number",
    "token",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: DaikinOnectaConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry without refreshing the cloud data."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "config_entry": entry.as_dict(),
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "rate_limits": coordinator.api.rate_limits,
            },
            "devices": [
                device.device.to_dict() for device in (coordinator.data or {}).values()
            ],
        },
        TO_REDACT,
    )
