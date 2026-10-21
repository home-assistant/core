"""The Rotarex integration."""

from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RotarexDataUpdateCoordinator

PLATFORMS: Final = [Platform.SENSOR]

type RotarexConfigEntry = ConfigEntry[RotarexDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RotarexConfigEntry) -> None:
    """Set up Rotarex from a config entry."""
    coordinator = RotarexDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: RotarexConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
