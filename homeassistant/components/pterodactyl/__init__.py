"""The Pterodactyl integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PterodactylConfigEntry, PterodactylCoordinator

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PterodactylConfigEntry) -> bool:
    """Set up Pterodactyl from a config entry."""
    coordinator = PterodactylCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PterodactylConfigEntry
) -> bool:
    """Unload a Pterodactyl config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
