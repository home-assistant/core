"""The TrestSolarController integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TrestDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

TrestConfigEntry = ConfigEntry[TrestDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TrestConfigEntry) -> bool:
    """Set up TrestSolarController from a config entry."""
    coordinator = TrestDataCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
