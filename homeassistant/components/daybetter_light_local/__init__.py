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

    try:
        await coordinator.start()
    except OSError as ex:
        if ex.errno != EADDRINUSE:
            _LOGGER.error("Start failed, errno: %d", ex.errno)
            return False
        _LOGGER.error("Port %s already in use", LISTENING_PORT)
        raise ConfigEntryNotReady from ex

    # 立即刷新数据以获取设备列表
    try:
        await coordinator.async_refresh()
    except Exception as ex:
        await coordinator.cleanup().wait()
        raise ConfigEntryNotReady(f"Failed to refresh data: {ex}") from ex

    # 关键修复：检查协调器数据，如果为空则重试
    if not coordinator.data:
        await coordinator.async_refresh()  # 再次尝试刷新

    # 检查是否有设备
    if not coordinator.data or len(coordinator.data) == 0:
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
