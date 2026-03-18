"""Diagnostics for the EHEIM Digital integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import EheimDigitalConfigEntry

TO_REDACT = {"emailAddr", "usrName"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EheimDigitalConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {"entry": entry.as_dict(), "data": entry.runtime_data.data}, TO_REDACT
    )
