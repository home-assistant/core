"""Diagnostics support for tedee."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import TedeeConfigEntry

TO_REDACT = {
    "lock_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TedeeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    # dict has sensitive info as key, redact manually
    data = {
        index: lock.to_dict()
        for index, (_, lock) in enumerate(coordinator.tedee_client.locks_dict.items())
    }
    return async_redact_data(data, TO_REDACT)
