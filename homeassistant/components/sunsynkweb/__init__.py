"""The Sunsynk Inverter Web integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PlantUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


type SunsyncConfigEntry = ConfigEntry[PlantUpdateCoordinator]

async def async_setup_entry(hass: HomeAssistant, entry: SunsyncConfigEntry ) -> bool:
    """Set up the Sunsynkweb coordinator from a config entry."""

    coordinator = PlantUpdateCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
