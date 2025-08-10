"""Tests for BLE Wi-Fi credential transmission in Grid Connect integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.grid_connect import ble_wifi


@pytest.mark.asyncio
async def test_format_wifi_payload():
    """Test Wi-Fi payload formatting."""
    ssid = "TestSSID"
    password = "TestPass"
    payload = ble_wifi.format_wifi_payload(ssid, password)
    assert payload == b"TestSSID,TestPass"

@pytest.mark.asyncio
async def test_send_wifi_credentials_success():
    """Test successful Wi-Fi credential transmission."""
    address = "AA:BB:CC:DD:EE:FF"
    ssid = "TestSSID"
    password = "TestPass"
    # Patch BleakClient and its methods
    with patch("homeassistant.components.grid_connect.ble_wifi.BleakClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.is_connected = AsyncMock(return_value=True)
        mock_instance.write_gatt_char = AsyncMock(return_value=None)
        result = await ble_wifi.send_wifi_credentials(address, ssid, password)
        assert result is None
        mock_instance.write_gatt_char.assert_awaited_once()

@pytest.mark.asyncio
async def test_send_wifi_credentials_not_connected():
    """Test Wi-Fi credential transmission failure when device is not connected."""
    address = "AA:BB:CC:DD:EE:FF"
    ssid = "TestSSID"
    password = "TestPass"
    with patch("homeassistant.components.grid_connect.ble_wifi.BleakClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.is_connected = AsyncMock(return_value=False)
        result = await ble_wifi.send_wifi_credentials(address, ssid, password)
        assert result == "not_connected"

@pytest.mark.asyncio
async def test_send_wifi_credentials_bleak_not_installed(monkeypatch):
    """Test Wi-Fi credential transmission failure when BleakClient is not installed."""
    monkeypatch.setattr(ble_wifi, "BleakClient", None)
    result = await ble_wifi.send_wifi_credentials("AA:BB:CC:DD:EE:FF", "ssid", "pass")
    assert result == "bleak_not_installed"

@pytest.mark.asyncio
async def test_send_wifi_credentials_timeout():
    """Test Wi-Fi credential transmission failure when device times out."""
    address = "AA:BB:CC:DD:EE:FF"
    ssid = "TestSSID"
    password = "TestPass"
    with patch("homeassistant.components.grid_connect.ble_wifi.BleakClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.is_connected = AsyncMock(return_value=True)
        mock_instance.write_gatt_char = AsyncMock(side_effect=TimeoutError)
        result = await ble_wifi.send_wifi_credentials(address, ssid, password)
        assert result == "timeout"

@pytest.mark.asyncio
async def test_send_wifi_credentials_unexpected_exception():
    """Test Wi-Fi credential transmission failure when an unexpected exception occurs."""
    address = "AA:BB:CC:DD:EE:FF"
    ssid = "TestSSID"
    password = "TestPass"
    with patch("homeassistant.components.grid_connect.ble_wifi.BleakClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.is_connected = AsyncMock(return_value=True)
        mock_instance.write_gatt_char = AsyncMock(side_effect=Exception("fail"))
        with pytest.raises(Exception) as excinfo:
            await ble_wifi.send_wifi_credentials(address, ssid, password)
        assert str(excinfo.value) == "fail"
