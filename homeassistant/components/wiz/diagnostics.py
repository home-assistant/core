"""Diagnostics support for WiZ."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import WizData

TO_REDACT = {"roomId", "homeId"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    wiz_data: WizData = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "data": async_redact_data(wiz_data.bulb.diagnostics, TO_REDACT),
    }
