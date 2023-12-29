"""The Govee Lights - Local API integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import GoveeLocalApiCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Local API from a config entry."""

    hass.async_add_job(hass.config_entries.async_forward_entry_setups(entry, PLATFORMS))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    entry_id = entry.entry_id

    coordinator: GoveeLocalApiCoordinator = hass.data.setdefault(DOMAIN, {}).get(
        entry_id
    )
    if coordinator:
        coordinator.clenaup()
        del hass.data[DOMAIN][entry_id]
        del hass.data[DOMAIN]

    return True
