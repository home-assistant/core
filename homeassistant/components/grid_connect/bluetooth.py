"""Bluetooth discovery module for Grid Connect integration."""

import logging

from bleak import BleakScanner

_LOGGER = logging.getLogger(__name__)


async def discover_bluetooth_devices():
    """Discover Bluetooth devices."""
    devices = await BleakScanner.discover()
    for device in devices:
        _LOGGER.info("Found device: %s, %s", device.name, device.address)
    return devices
