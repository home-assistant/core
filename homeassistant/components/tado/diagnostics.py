"""Provides diagnostics for Tado."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import TadoConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TadoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Tado config entry."""

    return {"data": config_entry.runtime_data.data}
