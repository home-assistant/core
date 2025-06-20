"""Integration for Crownstone."""

from __future__ import annotations

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .entry_manager import CrownstoneConfigEntry, CrownstoneEntryManager


async def async_setup_entry(hass: HomeAssistant, entry: CrownstoneConfigEntry) -> bool:
    """Initiate setup for a Crownstone config entry."""
    manager = CrownstoneEntryManager(hass, entry)

    if not await manager.async_setup():
        return False

    entry.runtime_data = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # HA specific listeners
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, manager.on_shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CrownstoneConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.async_unload()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(
    hass: HomeAssistant, entry: CrownstoneConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
