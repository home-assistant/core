"""Switcher integration helpers functions."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from aioswitcher.api.remotes import SwitcherBreezeRemoteManager
from aioswitcher.bridge import SwitcherBase, SwitcherBridge

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton

from .const import DATA_BRIDGE, DISCOVERY_TIME_SEC, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_start_bridge(
    hass: HomeAssistant, on_device_callback: Callable[[SwitcherBase], Any]
) -> None:
    """Start switcher UDP bridge."""
    bridge = hass.data[DOMAIN][DATA_BRIDGE] = SwitcherBridge(on_device_callback)
    _LOGGER.debug("Starting Switcher bridge")
    await bridge.start()


async def async_stop_bridge(hass: HomeAssistant) -> None:
    """Stop switcher UDP bridge."""
    bridge: SwitcherBridge = hass.data[DOMAIN].get(DATA_BRIDGE)
    if bridge is not None:
        _LOGGER.debug("Stopping Switcher bridge")
        await bridge.stop()
        hass.data[DOMAIN].pop(DATA_BRIDGE)


async def async_discover_devices() -> dict[str, SwitcherBase]:
    """Discover Switcher devices."""
    _LOGGER.debug("Starting discovery")
    discovered_devices = {}

    @callback
    def on_device_data_callback(device: SwitcherBase) -> None:
        """Use as a callback for device data."""
        if device.device_id in discovered_devices:
            return

        discovered_devices[device.device_id] = device

    bridge = SwitcherBridge(on_device_data_callback)
    await bridge.start()
    await asyncio.sleep(DISCOVERY_TIME_SEC)
    await bridge.stop()

    _LOGGER.debug("Finished discovery, discovered devices: %s", len(discovered_devices))
    return discovered_devices


@singleton.singleton("switcher_breeze_remote_manager")
def get_breeze_remote_manager(hass: HomeAssistant) -> SwitcherBreezeRemoteManager:
    """Get Switcher Breeze remote manager."""
    return SwitcherBreezeRemoteManager()
