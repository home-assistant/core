"""Diagnostics support for Bring."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import BringConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BringConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {k: v.to_dict() for k, v in config_entry.runtime_data.data.items()}
