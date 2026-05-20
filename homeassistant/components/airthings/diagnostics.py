"""Diagnostics support for Airthings."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from .const import CONF_SECRET
from .coordinator import AirthingsConfigEntry

REDACT_CONFIG = {CONF_SECRET, CONF_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirthingsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    coordinator_data: dict[str, Any] = {}

    if coordinator is not None:
        coordinator_data = {
            device_id: asdict(device) for device_id, device in coordinator.data.items()
        }

    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "coordinator_data": coordinator_data,
    }
