"""Diagnostics support for Sensirion BLE."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .const import DOMAIN

CONF_TITLE = "title"

TO_REDACT = {
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Collect processor data if available
    processor_data = {}
    if hasattr(coordinator, "_processors") and coordinator._processors:
        processor = coordinator._processors[0]  # Get the first processor
        if hasattr(processor, "data"):
            processor_data = {
                "entity_data": dict(processor.data.entity_data),
                "entity_names": dict(processor.data.entity_names),
                "devices": dict(processor.data.devices),
            }

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "coordinator_data": {
                "last_update_success": coordinator.last_update_success,
                "available": coordinator.available,
                "address": coordinator.address,
                "mode": str(coordinator.mode),
            },
            "processor_data": processor_data,
        },
        TO_REDACT,
    )
