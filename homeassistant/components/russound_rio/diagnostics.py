"""Diagnostics platform for Russound RIO."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import RussoundConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RussoundConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the provided config entry."""
    return entry.runtime_data.state
