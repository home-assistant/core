"""Diagnostics for Screenlogic."""

from typing import Any

from homeassistant.core import HomeAssistant

from .types import ScreenLogicConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ScreenLogicConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        "config_entry": config_entry.as_dict(),
        "data": coordinator.gateway.get_data(),
        "debug": coordinator.gateway.get_debug(),
    }
