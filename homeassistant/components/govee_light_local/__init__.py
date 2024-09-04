"""The Govee Light local integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging

from govee_local_api.controller import LISTENING_PORT

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DISCOVERY_TIMEOUT, DOMAIN
from .coordinator import GoveeLocalApiCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee light local from a config entry."""

    coordinator: GoveeLocalApiCoordinator = GoveeLocalApiCoordinator(hass=hass)

    async def await_cleanup():
        cleanup_complete: asyncio.Event = coordinator.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete.wait(), 1)

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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
