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
    data: dict[str, Any] = {"entry": entry.as_dict()}
    if hasattr(entry, "runtime_data"):
        data["measurement"] = entry.runtime_data.data
        data["last_update_success"] = entry.runtime_data.last_update_success
    return async_redact_data(data, TO_REDACT)
