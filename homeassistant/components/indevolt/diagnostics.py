"""Diagnostics support for Indevolt integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL_NUMBER
from .coordinator import IndevoltConfigEntry

# Redact sensitive information from diagnostics (host and serial numbers)
TO_REDACT = {
    CONF_HOST,
    CONF_SERIAL_NUMBER,
    "0",
    "9008",
    "9032",
    "9051",
    "9070",
    "9218",
    "9165",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IndevoltConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    device_info = {
        "model": coordinator.device_model,
        "generation": coordinator.generation,
        "serial_number": coordinator.serial_number,
        "firmware_version": coordinator.firmware_version,
    }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "device": async_redact_data(device_info, TO_REDACT),
        "coordinator_data": async_redact_data(coordinator.data, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
    }
