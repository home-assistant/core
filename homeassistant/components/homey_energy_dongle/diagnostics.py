"""Diagnostics support for the Homey Energy Dongle."""

import json
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import HomeyEnergyDongleConfigEntry

TO_REDACT = {"unique_id", "EQUIPMENT_IDENTIFIER", "MBUS_EQUIPMENT_IDENTIFIER"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeyEnergyDongleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "connected": coordinator.last_update_success,
            "telegram": json.loads(coordinator.data.to_json()),
        },
        TO_REDACT,
    )
