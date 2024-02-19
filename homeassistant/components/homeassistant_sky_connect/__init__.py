"""The Home Assistant SkyConnect integration."""
from __future__ import annotations

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    check_multi_pan_addon,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant SkyConnect config entry."""

    try:
        await check_multi_pan_addon(hass)
    except HomeAssistantError as err:
        raise ConfigEntryNotReady from err

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
