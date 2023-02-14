"""Tests for the Bluetooth integration."""
from unittest.mock import patch

import bleak
from bleak.backends.device import BLEDevice
import bleak_retry_connector
import pytest

from homeassistant.components.bluetooth.usage import (
    install_multiple_bleak_catcher,
    uninstall_multiple_bleak_catcher,
)
from homeassistant.components.bluetooth.wrappers import (
    HaBleakClientWrapper,
    HaBleakScannerWrapper,
)
from homeassistant.core import HomeAssistant

from . import _get_manager

MOCK_BLE_DEVICE = BLEDevice(
    "00:00:00:00:00:00", "any", delegate="", details={"path": "/dev/hci0/device"}
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


async def test_wrapping_bleak_client(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test we wrap BleakClient."""
    install_multiple_bleak_catcher()

    instance = bleak.BleakClient(MOCK_BLE_DEVICE)

    assert isinstance(instance, HaBleakClientWrapper)

    uninstall_multiple_bleak_catcher()

    instance = bleak.BleakClient(MOCK_BLE_DEVICE)

    assert not isinstance(instance, HaBleakClientWrapper)


async def test_bleak_client_reports_with_address(
    hass: HomeAssistant, enable_bluetooth: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we report when we pass an address to BleakClient."""
    install_multiple_bleak_catcher()

    with patch.object(
        _get_manager(),
        "async_ble_device_from_address",
        return_value=MOCK_BLE_DEVICE,
    ):
        instance = bleak.BleakClient("00:00:00:00:00:00")

    assert "BleakClient with an address instead of a BLEDevice" in caplog.text

    assert isinstance(instance, HaBleakClientWrapper)

    uninstall_multiple_bleak_catcher()

    caplog.clear()

    instance = bleak.BleakClient("00:00:00:00:00:00")

    assert not isinstance(instance, HaBleakClientWrapper)
    assert "BleakClient with an address instead of a BLEDevice" not in caplog.text


async def test_bleak_retry_connector_client_reports_with_address(
    hass: HomeAssistant, enable_bluetooth: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we report when we pass an address to BleakClientWithServiceCache."""
    install_multiple_bleak_catcher()

    with patch.object(
        _get_manager(),
        "async_ble_device_from_address",
        return_value=MOCK_BLE_DEVICE,
    ):
        instance = bleak_retry_connector.BleakClientWithServiceCache(
            "00:00:00:00:00:00"
        )

    assert "BleakClient with an address instead of a BLEDevice" in caplog.text

    assert isinstance(instance, HaBleakClientWrapper)

    uninstall_multiple_bleak_catcher()

    caplog.clear()

    instance = bleak_retry_connector.BleakClientWithServiceCache("00:00:00:00:00:00")

    assert not isinstance(instance, HaBleakClientWrapper)
    assert "BleakClient with an address instead of a BLEDevice" not in caplog.text
