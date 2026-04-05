"""Diagnostics support for the Teleinfo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import TeleinfoConfigEntry

TO_REDACT = {"ADCO"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TeleinfoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator_data": async_redact_data(dict(entry.runtime_data.data), TO_REDACT),
    }
