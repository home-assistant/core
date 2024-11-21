"""The Pure Energie integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import PureEnergieDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type PureEnergieConfigEntry = ConfigEntry[PureEnergieDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PureEnergieConfigEntry) -> bool:
    """Set up Pure Energie from a config entry."""

    coordinator = PureEnergieDataUpdateCoordinator(hass)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.gridnet.close()
        raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PureEnergieConfigEntry
) -> bool:
    """Unload Pure Energie config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
