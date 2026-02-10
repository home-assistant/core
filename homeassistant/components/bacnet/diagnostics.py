"""Diagnostics support for the BACnet integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    diagnostics: dict[str, Any] = {
        "entry_data": dict(entry.data),
        "client_connected": (
            runtime_data.client.is_connected
            if hasattr(runtime_data.client, "is_connected")
            else "unknown"
        ),
        "devices": {},
    }

    for device_key, coordinator in runtime_data.coordinators.items():
        device_info = coordinator.device_info
        device_diag: dict[str, Any] = {
            "device_info": {
                "device_id": device_info.device_id,
                "address": device_info.address,
                "name": device_info.name,
                "vendor_name": device_info.vendor_name,
                "model_name": device_info.model_name,
                "firmware_revision": device_info.firmware_revision,
            },
            "initial_setup_done": coordinator.initial_setup_done,
            "cov_subscriptions": coordinator.cov_subscription_count,
        }

        if coordinator.data is not None:
            device_diag["objects"] = [asdict(obj) for obj in coordinator.data.objects]
            device_diag["values"] = coordinator.data.values

        diagnostics["devices"][device_key] = device_diag

    return diagnostics
