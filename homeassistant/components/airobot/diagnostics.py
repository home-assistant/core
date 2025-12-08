"""Diagnostics support for Airobot."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import AirobotConfigEntry

TO_REDACT_CONFIG = [CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirobotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Build device capabilities info
    device_capabilities = None
    if coordinator.data:
        device_capabilities = {
            "has_floor_sensor": coordinator.data.status.has_floor_sensor,
            "has_co2_sensor": coordinator.data.status.has_co2_sensor,
            "hw_version": coordinator.data.status.hw_version,
            "fw_version": coordinator.data.status.fw_version,
        }

    return {
        "config_entry": {
            "title": entry.title,
            "state": entry.state.value,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "unique_id": entry.unique_id,
        },
        "entry_data": async_redact_data(entry.data, TO_REDACT_CONFIG),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
        },
        "device_capabilities": device_capabilities,
        "status": asdict(coordinator.data.status) if coordinator.data else None,
        "settings": asdict(coordinator.data.settings) if coordinator.data else None,
    }
