"""Diagnostics for Screenlogic."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    return {
        "config_entry": config_entry.as_dict(),
        "data": coordinator.gateway.get_data(),
        "debug": coordinator.gateway.get_debug(),
    }
