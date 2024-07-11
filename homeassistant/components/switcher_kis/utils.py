"""Switcher integration helpers functions."""

from __future__ import annotations

import asyncio
import logging

from aioswitcher.api.remotes import SwitcherBreezeRemoteManager
from aioswitcher.bridge import SwitcherBase, SwitcherBridge

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton

from .const import DISCOVERY_TIME_SEC

_LOGGER = logging.getLogger(__name__)


async def async_has_devices(hass: HomeAssistant) -> bool:
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
    return len(discovered_devices) > 0


@singleton.singleton("switcher_breeze_remote_manager")
def get_breeze_remote_manager(hass: HomeAssistant) -> SwitcherBreezeRemoteManager:
    """Get Switcher Breeze remote manager."""
    return SwitcherBreezeRemoteManager()
