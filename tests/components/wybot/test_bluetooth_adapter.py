"""Tests for the Home Assistant Bluetooth adapter."""

from unittest.mock import MagicMock, patch

from homeassistant.components.wybot.bluetooth_adapter import (
    HomeAssistantBluetoothAdapter,
)
from homeassistant.core import HomeAssistant


async def test_scanner_count(hass: HomeAssistant) -> None:
    """Test scanner count."""
    adapter = HomeAssistantBluetoothAdapter(hass)
    with patch(
        "homeassistant.components.wybot.bluetooth_adapter.async_scanner_count",
        return_value=3,
    ) as mock_count:
        assert adapter.scanner_count() == 3
    mock_count.assert_called_once_with(hass, connectable=True)


async def test_discovered_devices(hass: HomeAssistant) -> None:
    """Test discovered devices."""
    adapter = HomeAssistantBluetoothAdapter(hass)
    dev_a = MagicMock(name="dev_a")
    dev_b = MagicMock(name="dev_b")
    info_a = MagicMock()
    info_a.device = dev_a
    info_b = MagicMock()
    info_b.device = dev_b
    with patch(
        "homeassistant.components.wybot.bluetooth_adapter.async_discovered_service_info",
        return_value=[info_a, info_b],
    ) as mock_disc:
        assert adapter.discovered_devices() == [dev_a, dev_b]
    mock_disc.assert_called_once_with(hass, connectable=True)


async def test_device_from_address(hass: HomeAssistant) -> None:
    """Test device from address."""
    adapter = HomeAssistantBluetoothAdapter(hass)
    device = MagicMock(name="ble_device")
    with patch(
        "homeassistant.components.wybot.bluetooth_adapter.async_ble_device_from_address",
        return_value=device,
    ) as mock_from:
        assert adapter.device_from_address("AA:BB:CC:DD:EE:FF") is device
    mock_from.assert_called_once_with(hass, "AA:BB:CC:DD:EE:FF", connectable=True)


async def test_device_from_address_none(hass: HomeAssistant) -> None:
    """Test device from address none."""
    adapter = HomeAssistantBluetoothAdapter(hass)
    with patch(
        "homeassistant.components.wybot.bluetooth_adapter.async_ble_device_from_address",
        return_value=None,
    ):
        assert adapter.device_from_address("00:00:00:00:00:00") is None
