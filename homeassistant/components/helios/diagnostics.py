"""Diagnostics support for Helios."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import HeliosConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HeliosConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "coordinator_data": {
            "uuid": str(coordinator.data.uuid),
            "model": coordinator.data.model,
            "sw_version": coordinator.data.sw_version,
            "profile": str(coordinator.data.profile),
        },
    }
