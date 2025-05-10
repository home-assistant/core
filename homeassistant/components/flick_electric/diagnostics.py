"""Diagnostics for the Flick Electric integration."""

from typing import Any

from homeassistant.const import CONF_CLIENT_SECRET, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .coordinator import FlickConfigEntry

TO_REDACT = [
    CONF_PASSWORD,
    CONF_CLIENT_SECRET,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FlickConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": entry.runtime_data.data.raw,
    }
