"""Diagnostics for Screenlogic."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import ScreenlogicDataUpdateCoordinator
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    return {
        "config_entry": config_entry.as_dict(),
        "data": coordinator.data,
    }
