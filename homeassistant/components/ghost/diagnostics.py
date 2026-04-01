"""Diagnostics support for Ghost."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import GhostConfigEntry
from .const import CONF_ADMIN_API_KEY

TO_REDACT = {CONF_ADMIN_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: GhostConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "entry_data": dict(config_entry.data),
            "coordinator_data": asdict(config_entry.runtime_data.coordinator.data),
        },
        TO_REDACT,
    )
