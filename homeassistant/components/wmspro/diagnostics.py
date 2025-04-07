"""Diagnostics support for WMS WebControl pro API integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import WebControlProConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return entry.runtime_data.diag()
