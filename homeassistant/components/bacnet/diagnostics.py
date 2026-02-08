"""Diagnostics support for the BACnet integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_HUB


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type == ENTRY_TYPE_HUB:
        return _get_hub_diagnostics(entry)

    return _get_device_diagnostics(entry)


def _get_hub_diagnostics(entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a hub entry."""
    runtime_data = entry.runtime_data
    return {
        "entry_data": dict(entry.data),
        "client_connected": (
            runtime_data.client.is_connected
            if hasattr(runtime_data, "client")
            and hasattr(runtime_data.client, "is_connected")
            else "unknown"
        ),
        "hub_device_id": (
            runtime_data.hub_device_id
            if hasattr(runtime_data, "hub_device_id")
            else "unknown"
        ),
    }


def _get_device_diagnostics(entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    coordinator = entry.runtime_data.coordinator
    device_info = coordinator.device_info

    diagnostics: dict[str, Any] = {
        "entry_data": dict(entry.data),
        "entry_options": dict(entry.options),
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
        diagnostics["objects"] = [asdict(obj) for obj in coordinator.data.objects]
        diagnostics["values"] = coordinator.data.values

    return diagnostics
