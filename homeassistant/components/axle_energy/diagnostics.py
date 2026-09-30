"""Diagnostics support for Axle Energy."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import AxleConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AxleConfigEntry
) -> dict[str, Any]:
    """Return cached event data without requesting an update."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "data": asdict(coordinator.data) if coordinator.data is not None else None,
    }
