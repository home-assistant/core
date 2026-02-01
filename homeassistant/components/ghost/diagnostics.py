"""Diagnostics support for Ghost."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import GhostConfigEntry
from .const import CONF_ADMIN_API_KEY

TO_REDACT = {CONF_ADMIN_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GhostConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator_data": coordinator.data,
        "last_update_success": coordinator.last_update_success,
        "webhooks_enabled": entry.runtime_data.webhooks_enabled,
        "webhook_count": len(entry.runtime_data.ghost_webhook_ids),
    }
