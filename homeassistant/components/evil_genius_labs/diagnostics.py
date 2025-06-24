"""Diagnostics support for Evil Genius Labs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import EvilGeniusConfigEntry

TO_REDACT = {"wiFiSsidDefault", "wiFiSSID"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: EvilGeniusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        "info": async_redact_data(coordinator.info, TO_REDACT),
        "all": coordinator.data,
    }
