"""The SimpleFIN integration."""

from __future__ import annotations

from simplefin4py import SimpleFin

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_URL
from .coordinator import SimpleFinDataUpdateCoordinator

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


type SimpleFinConfigEntry = ConfigEntry[SimpleFinDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SimpleFinConfigEntry) -> bool:
    """Set up from a config entry."""
    access_url = entry.data[CONF_ACCESS_URL]
    sf_client = SimpleFin(access_url)
    sf_coordinator = SimpleFinDataUpdateCoordinator(hass, sf_client)
    await sf_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = sf_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
