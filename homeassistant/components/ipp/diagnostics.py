"""Diagnostics support for Internet Printing Protocol (IPP)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import IPPConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: IPPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        "entry": {
            "data": {
                **config_entry.data,
            },
            "unique_id": config_entry.unique_id,
        },
        "data": coordinator.data.as_dict(),
    }
