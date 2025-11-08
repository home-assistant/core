"""Switcher integration helpers functions."""

from __future__ import annotations

import asyncio
import logging

from aioswitcher.api import SwitcherApi
from aioswitcher.api.messages import SwitcherStateResponse
from aioswitcher.api.remotes import SwitcherBreezeRemoteManager
from aioswitcher.bridge import SwitcherBridge
from aioswitcher.device import DeviceType, SwitcherBase

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


async def async_test_device_connection(
    ip_address: str,
    device_id: str,
    device_key: str,
    device_type: DeviceType | None = None,
) -> SwitcherStateResponse:
    """Test connection to a Switcher device and retrieve its state.

    Returns the device state response if successful.
    Raises an exception if connection fails.
    """
    _LOGGER.info(
        "Testing connection to device at %s with device_id=%s, device_type=%s",
        ip_address,
        device_id,
        device_type.value if device_type else "None",
    )

    if device_type is None:
        raise ValueError("Device type must be specified")

    try:
        async with SwitcherApi(
            device_type,
            ip_address,
            device_id,
            device_key,
        ) as api:
            response = await api.get_state()
    except (TimeoutError, OSError) as err:
        _LOGGER.error(
            "Network error connecting to device at %s: %s. "
            "Verify the IP address is correct and the device is reachable.",
            ip_address,
            err,
        )
        raise TimeoutError(f"Cannot reach device at {ip_address}") from err
    except RuntimeError as err:
        _LOGGER.error(
            "Authentication failed for device at %s (device_id=%s, device_type=%s): %s. "
            "Verify device ID, device key, and device type are correct.",
            ip_address,
            device_id,
            device_type.value,
            err,
        )
        raise ValueError("Invalid device credentials or device type") from err
    else:
        if not response or not response.successful:
            _LOGGER.error("Device at %s returned unsuccessful response", ip_address)
            raise ConnectionError(f"Failed to get state from device at {ip_address}")

        _LOGGER.info("Successfully connected to device at %s", ip_address)
        return response


@singleton.singleton("switcher_breeze_remote_manager")
def get_breeze_remote_manager(hass: HomeAssistant) -> SwitcherBreezeRemoteManager:
    """Get Switcher Breeze remote manager."""
    return SwitcherBreezeRemoteManager()
