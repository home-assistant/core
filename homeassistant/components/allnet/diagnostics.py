"""Diagnostics support for ALLNET."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import AllnetConfigEntry
from .const import CONF_USE_SSL

REDACTED = "**REDACTED**"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AllnetConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    ha_device = runtime.ha_device_info

    # Sanitise entry data — redact password
    entry_data: dict[str, Any] = {**entry.data}
    if CONF_PASSWORD in entry_data:
        entry_data[CONF_PASSWORD] = REDACTED

    # Summarise known channels by kind
    channels_by_kind: dict[str, list[dict[str, Any]]] = {}
    for channel in (coordinator.data or {}).values():
        entry_channels = channels_by_kind.setdefault(channel.kind, [])
        entry_channels.append(
            {
                "id": channel.id,
                "name": channel.name,
                "unit": channel.unit,
                "available": channel.value is not None,
            }
        )

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
            "data": entry_data,
            "options": dict(entry.options),
        },
        "device": {
            "manufacturer": ha_device.get("manufacturer"),
            "model": ha_device.get("model"),
            "sw_version": ha_device.get("sw_version"),
            "hw_version": ha_device.get("hw_version"),
            "configuration_url": ha_device.get("configuration_url"),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "update_interval_seconds": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
        },
        "channels": channels_by_kind,
        "channel_count": sum(len(v) for v in channels_by_kind.values()),
    }
