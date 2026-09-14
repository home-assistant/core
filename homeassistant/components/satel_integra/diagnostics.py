"""Diagnostics support for Satel Integra."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant

from .const import CONF_ENCRYPTION_KEY
from .coordinator import SatelConfigEntry

TO_REDACT = {CONF_CODE, CONF_ENCRYPTION_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SatelConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    return {
        "config_entry_data": async_redact_data(entry.data, TO_REDACT),
        "config_entry_options": async_redact_data(entry.options, TO_REDACT),
        "subentries": dict(entry.subentries),
        "panel_info": (
            asdict(entry.runtime_data.panel_info)
            if entry.runtime_data.panel_info
            else None
        ),
    }
