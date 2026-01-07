"""Diagnostics support for LIFX."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_MAC
from homeassistant.core import HomeAssistant

from .const import CONF_LABEL
from .coordinator import LIFXConfigEntry

TO_REDACT = [CONF_LABEL, CONF_HOST, CONF_IP_ADDRESS, CONF_MAC]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LIFXConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a LIFX config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "data": async_redact_data(await coordinator.diagnostics(), TO_REDACT),
    }
