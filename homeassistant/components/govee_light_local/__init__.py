"""The Govee Light local integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging

from govee_local_api.controller import LISTENING_PORT

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DISCOVERY_TIMEOUT
from .coordinator import GoveeLocalApiCoordinator, GoveeLocalConfigEntry

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def update_listener(
    hass: HomeAssistant, config_entry: GoveeLocalConfigEntry
) -> None:
    """Handle options update."""
    coordinator: GoveeLocalApiCoordinator = config_entry.runtime_data

    if devices := config_entry.options.get("manual_devices", set()):
        for device in devices:
            if coordinator.get_device_by_ip(device) is None:
                coordinator.add_device_to_discovery_queue(device)

    if enable_discovery := config_entry.options.get("auto_discovery"):
        coordinator.enable_discovery(enable_discovery)


async def async_setup_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> bool:
    """Set up Govee light local from a config entry."""
    coordinator = GoveeLocalApiCoordinator(hass, entry)

    async def await_cleanup():
        cleanup_complete: asyncio.Event = coordinator.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete.wait(), 1)

    entry.async_on_unload(await_cleanup)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    if entry.options and "manual_devices" in entry.options:
        for device in entry.options["manual_devices"]:
            coordinator.add_device_to_discovery_queue(device)

    try:
        await coordinator.start()
    except OSError as ex:
        if ex.errno != EADDRINUSE:
            _LOGGER.error("Start failed, errno: %d", ex.errno)
            return False
        _LOGGER.error("Port %s already in use", LISTENING_PORT)
        raise ConfigEntryNotReady from ex

    await coordinator.async_config_entry_first_refresh()

    if entry.data.get("auto_discovery", True):
        try:
            async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
                while not coordinator.devices:
                    await asyncio.sleep(delay=1)
        except TimeoutError as ex:
            raise ConfigEntryNotReady from ex

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
