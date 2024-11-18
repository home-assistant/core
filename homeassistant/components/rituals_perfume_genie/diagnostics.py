"""Diagnostics support for Rituals Perfume Genie."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator

TO_REDACT = {
    "hublot",
    "hash",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    return {
        "diffusers": [
            async_redact_data(coordinator.diffuser.data, TO_REDACT)
            for coordinator in coordinators.values()
        ]
    }
