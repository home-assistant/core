"""Diagnostics support for Ollama."""

from typing import Any

from homeassistant.const import CONF_API_KEY, CONF_PROMPT
from homeassistant.core import HomeAssistant

from . import OllamaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OllamaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_version": f"{entry.version}.{entry.minor_version}",
        "state": entry.state.value,
        "api_key_configured": bool(entry.data.get(CONF_API_KEY)),
        "subentries": [
            {
                "title": subentry.title,
                "subentry_type": subentry.subentry_type,
                "data": {
                    key: value
                    for key, value in subentry.data.items()
                    if key != CONF_PROMPT
                },
            }
            for subentry in entry.subentries.values()
        ],
    }
