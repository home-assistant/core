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
    return {
        "diffusers": [
            async_redact_data(
                {
                    "hub": coordinator.data.hub.to_dict(),
                    "sensors": asdict(coordinator.data.sensors),
                },
                TO_REDACT,
            )
            for coordinator in entry.runtime_data.values()
        ]
    }
