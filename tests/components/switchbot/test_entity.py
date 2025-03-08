"""Test the switchbot covers."""

from unittest.mock import AsyncMock, Mock

from bleak.backends.device import BLEDevice
import pytest
from switchbot import SwitchbotDevice

from homeassistant.components.switchbot.coordinator import (
    SwitchbotDataUpdateCoordinator,
)
from homeassistant.components.switchbot.entity import SwitchbotEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_macos_address_skips_network_mac(hass: HomeAssistant) -> None:
    """Test wrong format mac address in MacOs."""
    ble_device = Mock()
    ble_device.address = "AABBCCDDEEFF"

    coordinator = Mock()
    coordinator.ble_device = ble_device
    coordinator.base_unique_id = "aabbccddeeff"
    coordinator.model = "test-name"
    coordinator.device_name = "curtain"

    entity = SwitchbotEntity(coordinator)
    assert (dr.CONNECTION_BLUETOOTH, "AABBCCDDEEFF") in entity.device_info[
        "connections"
    ]
    assert not any(
        conn[0] == dr.CONNECTION_NETWORK_MAC
        for conn in entity.device_info["connections"]
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_async_update_called() -> None:
    """Test async update method calls update on the device."""
    mock_device = Mock(spec=SwitchbotDevice)
    mock_device.update = AsyncMock()

    ble_device = Mock(spec=BLEDevice)
    ble_device.address = "AA:BB:CC:DD:EE:FF"

    mock_coordinator = Mock(spec=SwitchbotDataUpdateCoordinator)
    mock_coordinator.device = mock_device
    mock_coordinator.ble_device = ble_device
    mock_coordinator.base_unique_id = "aabbccddeeff"
    mock_coordinator.model = "test-name"
    mock_coordinator.device_name = "curtain"

    entity = SwitchbotEntity(mock_coordinator)

    await entity.async_update()

    mock_device.update.assert_awaited_once()
