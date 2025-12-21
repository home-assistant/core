"""Diagnostics support for WiZ."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import WizConfigEntry

TO_REDACT = {"roomId", "homeId"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WizConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "data": async_redact_data(entry.runtime_data.bulb.diagnostics, TO_REDACT),
    }
