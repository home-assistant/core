"""The Govee Light local integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging

from govee_local_api.controller import LISTENING_PORT

from homeassistant.components import network
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DISCOVERY_TIMEOUT
from .coordinator import GoveeLocalApiCoordinator, GoveeLocalConfigEntry

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GoveeLocalConfigEntry) -> bool:
    """Set up Govee light local from a config entry."""

    # Get source IPs for all enabled adapters
    source_ips = await network.async_get_enabled_source_ips(hass)
    _LOGGER.debug("Enabled source IPs: %s", source_ips)

    coordinator: GoveeLocalApiCoordinator = GoveeLocalApiCoordinator(
        hass=hass, config_entry=entry, source_ips=source_ips
    )

    async def await_cleanup():
        cleanup_complete_events: [asyncio.Event] = coordinator.cleanup()
        with suppress(TimeoutError):
            await asyncio.gather(
                *[
                    asyncio.wait_for(cleanup_complete_event.wait(), 1)
                    for cleanup_complete_event in cleanup_complete_events
                ]
            )

    entry.async_on_unload(await_cleanup)

    try:
        await coordinator.start()
    except OSError as ex:
        if ex.errno != EADDRINUSE:
            _LOGGER.error("Start failed, errno: %d", ex.errno)
            return False
        _LOGGER.error("Port %s already in use", LISTENING_PORT)
        raise ConfigEntryNotReady from ex

    await coordinator.async_config_entry_first_refresh()

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
