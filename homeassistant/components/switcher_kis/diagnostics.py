"""Diagnostics support for Switcher."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SwitcherConfigEntry

TO_REDACT = {"device_id", "device_key", "ip_address", "mac_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SwitcherConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = entry.runtime_data

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "devices": [asdict(coordinators[d].data) for d in coordinators],
        },
        TO_REDACT,
    )
