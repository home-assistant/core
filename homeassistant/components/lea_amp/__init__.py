"""The LEA AMP local integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import LEAAMPApiCoordinator, LEAAMPConfigEntry

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]
CONNECTION_TIMEOUT = 5  # seconds
PORT = "4321"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LEAAMPConfigEntry) -> bool:
    """Set up LEA AMP local from a config entry."""
    coordinator = LEAAMPApiCoordinator(hass, entry)

    async def await_cleanup():
        """Disable discovery, disable update, Close connections."""
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
        _LOGGER.error("Port %s already in use", PORT)
        raise ConfigEntryNotReady from ex

    await coordinator.async_config_entry_first_refresh()

    try:
        async with asyncio.timeout(delay=CONNECTION_TIMEOUT):
            while not coordinator.zones:
                await asyncio.sleep(delay=1)
    except TimeoutError as ex:
        raise ConfigEntryNotReady from ex

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LEAAMPConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
