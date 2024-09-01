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

pytestmark = pytest.mark.usefixtures("mock_automower_client")


async def test_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_registry.async_get_device(
        identifiers={(DOMAIN, AUTOMOWER_SERVICE_INFO.address)}
    )

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_retry_connect(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return False

    mock_automower_client.connect = _connect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failed_connect(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        raise BleakError

    mock_automower_client.connect = _connect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_disconnect_one(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_automower_client.connect = _connect_success

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data

    mock_automower_client.is_connected.return_value = False

    await coordinator._async_update_data()


async def test_setup_disconnect_two(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_automower_client.connect = _connect_success

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        raise BleakError

    mock_automower_client.connect = _connect
    mock_automower_client.is_connected.return_value = False

    coordinator = mock_config_entry.runtime_data

    try:
        await coordinator._async_update_data()
    except UpdateFailed:
        await coordinator.async_shutdown()


async def test_setup_disconnect_three(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_automower_client.connect = _connect_success

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    async def _connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return False

    mock_automower_client.connect = _connect
    mock_automower_client.is_connected.return_value = False

    coordinator = mock_config_entry.runtime_data

    try:
        await coordinator._async_update_data()
    except UpdateFailed:
        await coordinator.async_shutdown()


async def test_setup_disconnect_five(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_automower_client.connect = _connect_success

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    def _is_connected() -> bool:
        """Mock BleakClient.is_connected."""
        raise BleakError

    mock_automower_client.is_connected = _is_connected

    coordinator = mock_config_entry.runtime_data

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()


async def test_setup_invalid_mower_activity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_automower_client.connect = _connect_success
    mock_automower_client.is_connected.return_value = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    async def _mower_activity():
        return None

    og_mower_activity = mock_automower_client.mower_activity
    mock_automower_client.mower_activity = _mower_activity

    coordinator = mock_config_entry.runtime_data

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_automower_client.mower_activity = og_mower_activity


async def test_setup_invalid_mower_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_automower_client.connect = _connect_success
    mock_automower_client.is_connected.return_value = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    async def _mower_state():
        return None

    og_mower_state = mock_automower_client.mower_state
    mock_automower_client.mower_state = _mower_state

    coordinator = mock_config_entry.runtime_data

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_automower_client.mower_state = og_mower_state


async def test_setup_invalid_battery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    async def _connect_success(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    mock_automower_client.connect = _connect_success
    mock_automower_client.is_connected.return_value = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    og_battery_level = mock_automower_client.battery_level
    mock_automower_client.battery_level.return_value = None

    coordinator = mock_config_entry.runtime_data

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_automower_client.battery_level = og_battery_level


async def test_setup_exception_battery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    mock_automower_client.connect.return_value = True
    mock_automower_client.is_connected.return_value = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    async def _battery_level():
        raise BleakError

    og_battery_level = mock_automower_client.battery_level
    mock_automower_client.battery_level = _battery_level

    coordinator = mock_config_entry.runtime_data

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()

    mock_automower_client.battery_level = og_battery_level
