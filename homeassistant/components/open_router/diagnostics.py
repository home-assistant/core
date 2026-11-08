"""Diagnostics support for OpenRouter."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_PROMPT
from homeassistant.core import HomeAssistant

from . import OpenRouterConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_PROMPT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OpenRouterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "data": async_redact_data(entry.data, TO_REDACT),
        "subentries": {
            subentry.subentry_id: {
                "title": subentry.title,
                "subentry_type": subentry.subentry_type,
                "data": async_redact_data(subentry.data, TO_REDACT),
            }
            for subentry in entry.subentries.values()
        },
    }
