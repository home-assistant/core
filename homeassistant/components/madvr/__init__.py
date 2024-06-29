"""The madvr-envy integration."""

from __future__ import annotations

import logging

from madvr.madvr import Madvr

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import MadVRCoordinator

PLATFORMS: list[Platform] = [Platform.REMOTE]

type MadVRConfigEntry = ConfigEntry[MadVRCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: MadVRConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    madVRClient = Madvr(
        host=entry.data[CONF_HOST],
        logger=_LOGGER,
        port=entry.data[CONF_PORT],
        connect_timeout=10,
        loop=hass.loop,
    )
    coordinator = MadVRCoordinator(hass, madVRClient)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.add_update_listener(async_reload_entry)

    # handle loading operations
    await coordinator.handle_coordinator_load()
    return True


async def async_handle_unload(coordinator: MadVRCoordinator) -> None:
    """Handle unload."""
    _LOGGER.debug("Integration unloading")
    coordinator.client.stop()
    await coordinator.client.async_cancel_tasks()
    _LOGGER.debug("Integration closing connection")
    await coordinator.client.close_connection()
    _LOGGER.debug("Unloaded")


async def async_unload_entry(hass: HomeAssistant, entry: MadVRConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MadVRCoordinator = entry.runtime_data
        if coordinator:
            await async_handle_unload(coordinator=coordinator)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: MadVRConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
