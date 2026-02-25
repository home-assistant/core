"""The Kiosker integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import KioskerConfigEntry, KioskerDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]

# Limit concurrent updates to prevent overwhelming the API
PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: KioskerConfigEntry) -> bool:
    """Set up Kiosker from a config entry."""

    coordinator = KioskerDataUpdateCoordinator(
        hass,
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KioskerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
