"""Diagnostics support for OneDrive."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import OneDriveConfigEntry

TO_REDACT = {"display_name", "email", CONF_ACCESS_TOKEN, CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: OneDriveConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data.coordinator

    data = {
        "drive": asdict(coordinator.data),
        "config": {
            **entry.data,
            **entry.options,
        },
    }

    return async_redact_data(data, TO_REDACT)
