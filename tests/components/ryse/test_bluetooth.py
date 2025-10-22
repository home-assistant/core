"""Tests for the Ryse Bluetooth."""

from unittest.mock import AsyncMock, patch

import pytest
from ryseble.device import RyseBLEDevice


@pytest.fixture
def mock_ble_client():
    """Mock the BleakClient for BLE communication."""
    with patch("components.ryse.bluetooth.BleakClient") as mock_client:
        instance = mock_client.return_value
        instance.connect = AsyncMock(return_value=True)
        instance.start_notify = AsyncMock()
        instance.read_gatt_char = AsyncMock(return_value=b"\xf5\x03\x01\x01\x64")
        instance.write_gatt_char = AsyncMock()
        instance.disconnect = AsyncMock()
        instance.is_connected = True
        yield instance


@pytest.mark.asyncio
async def test_device_pairing(mock_ble_client) -> None:
    """Test BLE device pairing."""
    device = RyseBLEDevice("AA:BB:CC:DD:EE:FF", "rx_uuid", "tx_uuid")
    paired = await device.pair()

    assert paired is True
    mock_ble_client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_read_data(mock_ble_client) -> None:
    """Test reading data from BLE device."""
    device = RyseBLEDevice("AA:BB:CC:DD:EE:FF", "rx_uuid", "tx_uuid")
    await device.pair()

    data = await device.read_data()
    assert data == b"\xf5\x03\x01\x01\x64"


@pytest.mark.asyncio
async def test_write_data(mock_ble_client) -> None:
    """Test sending data to BLE device."""
    device = RyseBLEDevice("AA:BB:CC:DD:EE:FF", "rx_uuid", "tx_uuid")
    await device.pair()

    await device.write_data(b"\xf5\x03\x01\x01\x64")
    mock_ble_client.write_gatt_char.assert_called_once()
