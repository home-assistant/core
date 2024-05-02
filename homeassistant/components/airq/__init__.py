"""The air-Q integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AirQCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

AirQConfigEntry = ConfigEntry[AirQCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AirQConfigEntry) -> bool:
    """Set up air-Q from a config entry."""

    coordinator = AirQCoordinator(hass, entry)

    # Query the device for the first time and initialise coordinator.data
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirQConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
