"""Tests for the Bluetooth integration."""


import bleak

from homeassistant.components.bluetooth.models import HaBleakScannerWrapper
from homeassistant.components.bluetooth.usage import (
    install_multiple_bleak_catcher,
    uninstall_multiple_bleak_catcher,
)


async def test_multiple_bleak_scanner_instances(hass):
    """Test creating multiple BleakScanners without an integration."""
    install_multiple_bleak_catcher()

    instance = bleak.BleakScanner()

    assert isinstance(instance, HaBleakScannerWrapper)

    uninstall_multiple_bleak_catcher()

    instance = bleak.BleakScanner()

    assert not isinstance(instance, HaBleakScannerWrapper)
