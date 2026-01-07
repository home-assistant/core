"""Diagnostics support for Qube Heat Pump."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import QubeConfigEntry

TO_REDACT = {"host", "port", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QubeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    hub = data.hub

    summary = {
        "entry": {
            "entry_id": entry.entry_id,
            "data": entry.data,
            "options": entry.options,
        },
        "hub": {
            "host": getattr(hub, "host", None),
            "port": getattr(hub, "port", None),
            "label": getattr(hub, "label", None),
            "multi_device": data.multi_device,
        },
        "entities": [
            {
                "name": getattr(e, "name", None),
                "unique_id": getattr(e, "unique_id", None),
                "platform": getattr(e, "platform", None),
                "address": getattr(e, "address", None),
            }
            for e in list(getattr(hub, "entities", []))[:10]
        ],
    }
    return async_redact_data(summary, TO_REDACT)
