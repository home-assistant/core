"""Diagnostics support for La Marzocco."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import LaMarzoccoConfigEntry

TO_REDACT = {
    "serial_number",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.config_coordinator
    device = coordinator.device
    return async_redact_data(device.to_dict(), TO_REDACT)
