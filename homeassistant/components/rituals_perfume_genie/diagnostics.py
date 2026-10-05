"""Diagnostics support for Rituals Perfume Genie."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import RitualsConfigEntry

TO_REDACT = {
    "hublot",
    "hash",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RitualsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    return {
        "diffusers": [
            async_redact_data(
                {
                    "hub": hub.to_dict(),
                    "sensors": (
                        asdict(sensors.data)
                        if (sensors := runtime_data.sensors[hublot]).data
                        else None
                    ),
                },
                TO_REDACT,
            )
            for hublot, hub in runtime_data.hubs.data.items()
        ]
    }
