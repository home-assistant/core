"""Diagnostics platform for Cambridge Audio."""

from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from . import CambridgeAudioConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the provided config entry."""
    client = entry.runtime_data
    return async_redact_data(
        {"info": client.info, "sources": client.sources}, TO_REDACT
    )
