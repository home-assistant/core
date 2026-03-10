"""Diagnostics support for Flic Button."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import FlicButtonConfigEntry

TO_REDACT = {
    "pairing_key",
    "pairing_id",
    "button_uuid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FlicButtonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "device_type": (
                coordinator.device_type.value if coordinator.device_type else None
            ),
            "model_name": coordinator.model_name,
            "firmware_version": coordinator.firmware_version,
            "latest_firmware_version": coordinator.latest_firmware_version,
            "connected": coordinator.connected,
        },
        TO_REDACT,
    )
