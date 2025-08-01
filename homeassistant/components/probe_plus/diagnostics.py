"""Diagnostics for Probe Plus."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ProbePlusConfigEntry, ProbePlusDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ProbePlusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ProbePlusDataUpdateCoordinator = entry.runtime_data
    device = coordinator.device

    device_state_diagnostics = {}
    if device and device.device_state:
        device_state_diagnostics = {
            "probe_temperature": device.device_state.probe_temperature,
            "probe_battery": device.device_state.probe_battery,
            "relay_battery": device.device_state.relay_battery,
            "probe_rssi": device.device_state.probe_rssi,
            "relay_voltage": device.device_state.relay_voltage,
            "probe_voltage": device.device_state.probe_voltage,
        }

    device_info_diagnostics = {}
    if device:
        device_info_diagnostics = {
            "mac_address": device.mac,
            "name": device.name,
            "is_connected": device.connected,
        }

    return {
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "domain": entry.domain,
            "source": entry.source,
            "unique_id": entry.unique_id,
        },
        "device_info": device_info_diagnostics,
        "device_state": device_state_diagnostics,
    }
