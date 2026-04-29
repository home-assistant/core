"""Diagnostics support for Fumis."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import FumisConfigEntry

TO_REDACT_UNIT = {"id", "ip"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FumisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = await entry.runtime_data.client.raw_status()
    data["unit"] = async_redact_data(data["unit"], TO_REDACT_UNIT)
    return data
