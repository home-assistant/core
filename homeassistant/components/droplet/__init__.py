"""The Droplet integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .droplet import Droplet

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type DropletConfigEntry = ConfigEntry[Droplet]


async def async_setup_entry(hass: HomeAssistant, entry: DropletConfigEntry) -> bool:
    """Set up Droplet from a config entry."""

    # 1. Create API instance
    # 2. Validate the API connection (and authentication)
    # 3. Store an API object for your platforms to access
    # entry.runtime_data = MyAPI(...)
    # Yes... It should be 1 API here, multiple clients later...?

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DropletConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
