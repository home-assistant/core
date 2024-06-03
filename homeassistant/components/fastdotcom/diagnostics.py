"""Diagnostics support for Fast.com."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import FastdotcomDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    coordinator: FastdotcomDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    return {
        "coordinator_data": coordinator.data,
    }
