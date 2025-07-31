"""Test binary sensors for acaia integration."""

from unittest.mock import Mock

from bleak.exc import BleakError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.togrill.coordinator import (
    DeviceFailed,
    DeviceNotFound,
    ToGrillCoordinator,
)
from homeassistant.core import HomeAssistant

from . import TOGRILL_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_client_disconnect(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_client_class: Mock,
) -> None:
    """Test that coordinator handles a disconnected client."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [])

    coordinator: ToGrillCoordinator = mock_entry.runtime_data
    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_client.is_connected = False
    mock_client_class.connect.side_effect = BleakError("Failed to connect")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, DeviceFailed)


async def test_client_reconnect(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_client_class: Mock,
) -> None:
    """Test that coordinator handles a disconnected client, which then reconnects."""

    await setup_entry(hass, mock_entry, [])

    coordinator: ToGrillCoordinator = mock_entry.runtime_data
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, DeviceNotFound)

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await hass.async_block_till_done()
    assert coordinator.last_update_success
