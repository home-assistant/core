"""Diagnostics support for Growatt Server."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import GrowattConfigEntry

TO_REDACT = {"password", "token", "username"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {"config_entry": config_entry.as_dict()}

    data = getattr(config_entry, "runtime_data", None)
    if data is not None:
        diag["total_coordinator"] = data.total_coordinator.data
        diag["devices"] = {
            device_sn: {
                "device_type": coordinator.device_type,
                "data": coordinator.data,
            }
            for device_sn, coordinator in data.devices.items()
        }

    return async_redact_data(diag, TO_REDACT)
