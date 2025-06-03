"""Tests for the Bluetooth integration."""

from unittest.mock import patch

import bleak
from habluetooth.usage import (
    install_multiple_bleak_catcher,
    uninstall_multiple_bleak_catcher,
)
from habluetooth.wrappers import HaBleakClientWrapper, HaBleakScannerWrapper
import pytest

from homeassistant.core import HomeAssistant

from . import generate_ble_device

MOCK_BLE_DEVICE = generate_ble_device(
    "00:00:00:00:00:00",
    "any",
    delegate="",
    details={"path": "/dev/hci0/device"},
    rssi=-127,
)


async def test_multiple_bleak_scanner_instances(hass: HomeAssistant) -> None:
    """Test creating multiple BleakScanners without an integration."""
    install_multiple_bleak_catcher()

    instance = bleak.BleakScanner()

    assert isinstance(instance, HaBleakScannerWrapper)

    uninstall_multiple_bleak_catcher()

    with patch("bleak.get_platform_scanner_backend_type"):
        instance = bleak.BleakScanner()

    assert not isinstance(instance, HaBleakScannerWrapper)


@pytest.mark.usefixtures("enable_bluetooth")
async def test_wrapping_bleak_client(hass: HomeAssistant) -> None:
    """Test we wrap BleakClient."""
    install_multiple_bleak_catcher()

    instance = bleak.BleakClient(MOCK_BLE_DEVICE)

    assert isinstance(instance, HaBleakClientWrapper)

    uninstall_multiple_bleak_catcher()

    instance = bleak.BleakClient(MOCK_BLE_DEVICE)

    assert not isinstance(instance, HaBleakClientWrapper)
