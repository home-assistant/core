"""Diagnostics support for Linkplay."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import LinkPlayConfigEntry

TO_REDACT = {"MAC"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LinkPlayConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    return async_redact_data(
        {"device_info": data.bridge.to_dict()},
        TO_REDACT,
    )
