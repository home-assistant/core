"""Provides diagnostics for the Home Assistant Connect ZBT-2 integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import HomeAssistantConnectZBT2ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: HomeAssistantConnectZBT2ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {"config_entry": config_entry.as_dict()}
