"""Diagnostics support for RFXCOM RFXtrx."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import RfxtrxConfigEntry

TO_REDACT = {"host"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RfxtrxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }
