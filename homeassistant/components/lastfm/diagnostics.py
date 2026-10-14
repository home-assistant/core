"""Diagnostics support for LastFM."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import LastFMConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LastFMConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "options": async_redact_data(entry.options, TO_REDACT),
        "users": {
            username: asdict(user_data)
            for username, user_data in entry.runtime_data.data.items()
        },
    }
