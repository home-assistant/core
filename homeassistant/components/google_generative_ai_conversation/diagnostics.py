"""Diagnostics support for Google Generative AI Conversation."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    api_key = entry.data.get(CONF_API_KEY, "")
    return {
        CONF_API_KEY: f"REDACTED (length: {len(api_key)})",
    }
