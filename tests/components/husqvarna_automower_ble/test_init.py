"""Test the Husqvarna Automower Bluetooth setup."""

import contextlib
from unittest.mock import Mock

from bleak import BleakError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import AUTOMOWER_SERVICE_INFO

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_client")


async def test_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, AUTOMOWER_SERVICE_INFO.address)}
    )
    assert device == snapshot

    coordinator = mock_entry.runtime_data.coordinator
    await coordinator.async_shutdown()


async def test_setup_retry_connect(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return False

    mock_client.connect = _connect

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failed_connect(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        raise BleakError

    mock_client.connect = _connect

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_disconnect_one(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    coordinator = mock_entry.runtime_data.coordinator

    def _is_connected(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        return False

    mock_client.is_connected = _is_connected

    await coordinator._async_update_data()


async def test_setup_disconnect_two(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    def _is_connected(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        return False

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        raise BleakError

    mock_client.connect = _connect
    mock_client.is_connected = _is_connected

    coordinator = mock_entry.runtime_data.coordinator

    try:
        await coordinator._async_update_data()
    except UpdateFailed:
        await coordinator.async_shutdown()


async def test_setup_disconnect_three(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    def _is_connected(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        return False

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return False

    mock_client.connect = _connect
    mock_client.is_connected = _is_connected

    coordinator = mock_entry.runtime_data.coordinator

    try:
        await coordinator._async_update_data()
    except UpdateFailed:
        await coordinator.async_shutdown()


async def test_setup_disconnect_five(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    def _is_connected(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        raise BleakError

    mock_client.is_connected = _is_connected

    coordinator = mock_entry.runtime_data.coordinator

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()


async def test_setup_invalid_mower_activity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    def _is_connected_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        return True

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success
    mock_client.is_connected = _is_connected_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    async def _mower_activity(self, *args, **kwargs):
        return None

    og_mower_activity = mock_client.mower_activity
    mock_client.mower_activity = _mower_activity

    coordinator = mock_entry.runtime_data.coordinator

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_client.mower_activity = og_mower_activity


async def test_setup_invalid_mower_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    def _is_connected_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        return True

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success
    mock_client.is_connected = _is_connected_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    async def _mower_state(self, *args, **kwargs):
        return None

    og_mower_state = mock_client.mower_state
    mock_client.mower_state = _mower_state

    coordinator = mock_entry.runtime_data.coordinator

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_client.mower_state = og_mower_state


async def test_setup_invalid_battery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    def _is_connected_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        return True

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success
    mock_client.is_connected = _is_connected_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    async def _battery_level(self, *args, **kwargs):
        return None

    og_battery_level = mock_client.battery_level
    mock_client.battery_level = _battery_level

    coordinator = mock_entry.runtime_data.coordinator

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_client.battery_level = og_battery_level


async def test_setup_exception_battery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: Mock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    def _is_connected_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.is_connected."""
        return True

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_client.connect = _connect_success
    mock_client.is_connected = _is_connected_success

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    async def _battery_level(self, *args, **kwargs):
        raise BleakError

    og_battery_level = mock_client.battery_level
    mock_client.battery_level = _battery_level

    coordinator = mock_entry.runtime_data.coordinator

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_client.battery_level = og_battery_level
