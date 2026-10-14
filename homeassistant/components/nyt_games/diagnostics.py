"""Diagnostics support for NYT Games."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import NYTGamesConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NYTGamesConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return asdict(entry.runtime_data.data)
