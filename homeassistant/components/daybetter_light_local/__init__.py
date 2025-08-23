"""The DayBetter Light local integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging

from daybetter_local_api.controller import LISTENING_PORT

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import DayBetterLocalApiCoordinator, DayBetterLocalConfigEntry

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: DayBetterLocalConfigEntry
) -> bool:
    """Set up DayBetter light local from a config entry."""
    coordinator = DayBetterLocalApiCoordinator(hass, entry)

    # 先启动coordinator，然后检查设备
    try:
        await coordinator.start()
    except OSError as ex:
        if ex.errno != EADDRINUSE:
            _LOGGER.error("Start failed, errno: %d", ex.errno)
            return False
        _LOGGER.error("Port %s already in use", LISTENING_PORT)
        raise ConfigEntryNotReady from ex

    # 检查是否有设备
    try:
        await coordinator.async_config_entry_first_refresh()
        devices = coordinator.devices
    except Exception as ex:
        await coordinator.cleanup().wait()
        raise ConfigEntryNotReady from ex

    if not devices:
        await coordinator.cleanup().wait()
        raise ConfigEntryNotReady("No DayBetter devices found")

    async def await_cleanup():
        cleanup_complete: asyncio.Event = coordinator.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete.wait(), 1)

    entry.async_on_unload(await_cleanup)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DayBetterLocalConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
