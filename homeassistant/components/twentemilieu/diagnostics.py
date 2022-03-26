"""Diagnostics support for TwenteMilieu."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.data[CONF_ID]]
    return {
        waste_type: [waste_date.isoformat() for waste_date in waste_dates]
        for waste_type, waste_dates in coordinator.data.items()
    }
