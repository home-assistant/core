"""The Droplet integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import DropletConfigEntry, DropletDataCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> bool:
    """Set up Droplet from a config entry."""

    if TYPE_CHECKING:
        assert config_entry.unique_id is not None
    droplet_coordinator = DropletDataCoordinator(hass, config_entry)

    # Add more exceptions perhaps
    if not await droplet_coordinator.setup():
        raise ConfigEntryNotReady("Device is offline")

    config_entry.runtime_data = droplet_coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Reload entry when it's updated.
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> None:
    """Reload the config entry when it changed."""
    hass.config_entries.async_schedule_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
