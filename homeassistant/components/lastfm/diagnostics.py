"""Diagnostics support for LastFM."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_MAIN_USER, CONF_USERS
from .coordinator import LastFMConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_MAIN_USER, CONF_USERS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LastFMConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "options": async_redact_data(entry.options, TO_REDACT),
        "users": [asdict(user_data) for user_data in entry.runtime_data.data.values()],
    }
