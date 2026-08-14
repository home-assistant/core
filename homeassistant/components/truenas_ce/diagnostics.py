"""Diagnostics support for TrueNAS."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import TO_REDACT
from .coordinator import TrueNASConfigEntry, get_truenas_coordinator


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, config_entry: TrueNASConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = get_truenas_coordinator(config_entry)
    return {
        "entry": {
            "data": async_redact_data(config_entry.data, TO_REDACT),
            "options": async_redact_data(config_entry.options, TO_REDACT),
        },
        "data": async_redact_data(coordinator.ds, TO_REDACT) if coordinator else {},
    }
