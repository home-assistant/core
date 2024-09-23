"""Diagnostics support for Linkplay."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from . import LinkPlayConfigEntry

TO_REDACT = {CONF_HOST, CONF_MAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LinkPlayConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    return async_redact_data(
        {
            "device_info": asdict(data),
            "config_entry_data": entry.data,
        },
        TO_REDACT,
    )
