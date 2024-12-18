"""Provides diagnostics for slide_local."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import SlideConfigEntry

TO_REDACT = [
    CONF_PASSWORD,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: SlideConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data.data

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "slide_data": data,
    }
