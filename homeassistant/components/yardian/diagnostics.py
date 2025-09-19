"""Diagnostics support for Yardian integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import YardianUpdateCoordinator

TO_REDACT = {
    "access_token",
    "host",
    "serialNumber",
    "yid",
    "sIotcUid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: YardianUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    di = coordinator.device_info
    device = {
        "name": entry.title,
        "model": getattr(di, "model", None),
        "yid": coordinator.yid,
        "serialNumber": getattr(di, "serial_number", None),
    }

    # Sanitize zones to basic tuple [name, enabled]
    zones: list[list[Any]] = []
    for z in data.zones:
        if isinstance(z, list) and len(z) >= 2:
            zones.append([z[0], z[1]])
        else:
            zones.append([None, None])

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device": async_redact_data(device, TO_REDACT),
        "state": {
            "active_zones": sorted(data.active_zones),
            "zones": zones,
        },
        "oper_info": async_redact_data(data.oper_info, TO_REDACT),
    }
