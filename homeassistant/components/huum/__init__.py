"""The Huum integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import HuumDataUpdateCoordinator

type HuumConfigEntry = ConfigEntry[HuumDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HuumConfigEntry) -> bool:
    """Set up Huum from a config entry."""
    coordinator = HuumDataUpdateCoordinator(
        hass,
        config_entry=entry,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
