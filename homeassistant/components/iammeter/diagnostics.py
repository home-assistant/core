"""Redacted diagnostics for IAMMETER."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import IammeterConfigEntry

TO_REDACT = {"host", "username", "password", "sn", "mac", "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IammeterConfigEntry
) -> dict[str, Any]:
    """Return connection and parser state without local addresses or identity."""
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "measurement": entry.runtime_data.data,
            "last_update_success": entry.runtime_data.last_update_success,
        },
        TO_REDACT,
    )
