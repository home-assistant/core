"""Diagnostics support for Watts Vision+."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import WattsVisionConfigEntry

TO_REDACT = {
    "access_token",
    "refresh_token",
    "id_token",
    "profile_info",
}


def _get_coordinator_diagnostics(coordinator: Any) -> dict[str, Any]:
    """Extract diagnostics from a coordinator."""
    return {
        "last_update_success": coordinator.last_update_success,
        "update_interval": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None
        ),
        "last_exception": (
            str(coordinator.last_exception) if coordinator.last_exception else None
        ),
    }


def _device_to_dict(device: Any) -> dict[str, Any]:
    """Convert Device object to dict for diagnostics."""
    if not (is_dataclass(device) and not isinstance(device, type)):
        raise TypeError("Expected dataclass instance")
    return asdict(device)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WattsVisionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    hub_coordinator = runtime_data.hub_coordinator

    devices_diagnostics: dict[str, Any] = {}
    for device_id, device in hub_coordinator.data.items():
        device_coordinator = runtime_data.device_coordinators.get(device_id)

        device_data = _device_to_dict(device)

        if device_coordinator:
            device_data["coordinator"] = _get_coordinator_diagnostics(
                device_coordinator
            )

        devices_diagnostics[device_id] = device_data

    hub_diagnostics = _get_coordinator_diagnostics(hub_coordinator)
    hub_diagnostics["device_count"] = len(hub_coordinator.data)

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "hub_coordinator": hub_diagnostics,
        "devices": devices_diagnostics,
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: WattsVisionConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    runtime_data = entry.runtime_data
    hub_coordinator = runtime_data.hub_coordinator

    device_id = next(iter(device.identifiers))[1]

    device_data = hub_coordinator.data.get(device_id)
    if not device_data:
        return {"error": "Device not found in coordinator data"}

    device_coordinator = runtime_data.device_coordinators.get(device_id)

    diagnostics = _device_to_dict(device_data)

    if device_coordinator:
        diagnostics["coordinator"] = _get_coordinator_diagnostics(device_coordinator)

    return diagnostics
