"""The Huum integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: HuumConfigEntry) -> bool:
    """Set up Huum from a config entry."""
    coordinator = HuumDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
    )

    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: HuumConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
