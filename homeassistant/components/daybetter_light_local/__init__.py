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

    # 首次刷新（必要：建立初始数据）
    await coordinator.async_config_entry_first_refresh()

    # 没有设备 -> 重试
    if not coordinator.devices:
        raise ConfigEntryNotReady("No DayBetter devices found")

    try:
        await coordinator.start()
    except OSError as ex:
        if ex.errno == EADDRINUSE:
            _LOGGER.error("Port %s already in use", LISTENING_PORT)
            raise ConfigEntryNotReady("Port already in use") from ex
        _LOGGER.error("Failed to start coordinator, errno=%d", ex.errno)
        raise ConfigEntryNotReady(f"Start failed: {ex}") from ex

    try:
        await coordinator.async_refresh()
    except Exception as ex:
        await _async_cleanup(coordinator)
        raise ConfigEntryNotReady(f"Failed to refresh data: {ex}") from ex

    # 确认刷新后仍有设备，否则重试
    if not coordinator.data:
        await _async_cleanup(coordinator)
        raise ConfigEntryNotReady("No DayBetter devices found")

    # 注册清理逻辑
    entry.async_on_unload(lambda: _async_cleanup(coordinator))

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DayBetterLocalConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_cleanup(coordinator: DayBetterLocalApiCoordinator) -> None:
    """Ensure coordinator cleanup completes safely."""
    cleanup_complete: asyncio.Event = coordinator.cleanup()
    with suppress(TimeoutError):
        await asyncio.wait_for(cleanup_complete.wait(), 1)
