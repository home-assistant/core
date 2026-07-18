"""Diagnostics support for Gatus."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .coordinator import GatusConfigEntry

TO_REDACT = {CONF_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GatusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": [
            {
                "key": ep.key,
                "name": ep.name,
                "group": ep.group,
                "results": [
                    {
                        "success": r.success,
                        "status": r.status,
                    }
                    for r in ep.results
                ],
            }
            for ep in coordinator.data.values()
        ],
    }
