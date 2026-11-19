"""Diagnostics support for Workday."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import WorkdayConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WorkdayConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "config_entry": entry,
    }
