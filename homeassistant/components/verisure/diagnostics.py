"""Diagnostics support for Verisure."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import VerisureConfigEntry

TO_REDACT = {
    "date",
    "area",
    "deviceArea",
    "name",
    "time",
    "reportTime",
    "userString",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VerisureConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(entry.runtime_data.data, TO_REDACT)
