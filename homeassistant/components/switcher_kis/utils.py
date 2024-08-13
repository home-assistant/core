"""Switcher integration helpers functions."""

from __future__ import annotations

import asyncio
import logging

from aioswitcher.api.remotes import SwitcherBreezeRemoteManager
from aioswitcher.bridge import SwitcherBase, SwitcherBridge
from aioswitcher.device.tools import validate_token

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton

from .const import DISCOVERY_TIME_SEC

_LOGGER = logging.getLogger(__name__)


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


async def validate_input(username: str, token: str) -> bool:
    """Validate token by specifying username and token."""
    token_is_valid = await validate_token(username, token)
    if token_is_valid:
        _LOGGER.info("Token is valid")
        return True
    _LOGGER.info("Token is invalid")
    return False
