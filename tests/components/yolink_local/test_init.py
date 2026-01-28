"""Tests for the YoLink Local integration."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry

CONF_NET_ID = "net_id"
DOMAIN = "yolink_local"


# Test data
TEST_HOST = "192.168.1.100"
TEST_NET_ID = "test_net_id_123"
TEST_CLIENT_ID = "test_client_id"
TEST_CLIENT_SECRET = "test_client_secret"

TEST_CONFIG_DATA = {
    CONF_HOST: TEST_HOST,
    CONF_NET_ID: TEST_NET_ID,
    CONF_CLIENT_ID: TEST_CLIENT_ID,
    CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
}


@pytest.fixture
def mock_yolink_client():
    """Mock YoLinkLocalHubClient."""
    with patch(
        "homeassistant.components.yolink_local.YoLinkLocalHubClient"
    ) as mock_client_class:
        client = Mock()
        client.async_setup = AsyncMock()
        client.get_devices = Mock(return_value=[])
        client.async_unload = AsyncMock()
        mock_client_class.return_value = client
        yield client


@pytest.fixture
def mock_device():
    """Create a mock YoLink device."""
    device = Mock(spec=YoLinkDevice)
    device.device_id = "device_123"
    device.paired_device_id = None
    device.device_type = "DoorSensor"
    device.name = "Test Door Sensor"
    return device


@pytest.fixture
def mock_paired_devices():
    """Create a pair of mock YoLink devices (parent and child)."""
    parent = Mock(spec=YoLinkDevice)
    parent.device_id = "parent_device"
    parent.paired_device_id = None
    parent.device_type = "Hub"
    parent.name = "Test Hub"

    child = Mock(spec=YoLinkDevice)
    child.device_id = "child_device"
    child.paired_device_id = "parent_device"
    child.device_type = "Sensor"
    child.name = "Test Sensor"

    return parent, child


@pytest.fixture
def mock_coordinator():
    """Mock YoLinkLocalCoordinator."""
    with patch(
        "homeassistant.components.yolink_local.YoLinkLocalCoordinator"
    ) as mock_coord_class:
        coordinator = Mock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = {}
        mock_coord_class.return_value = coordinator
        yield mock_coord_class


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_yolink_client, mock_device, mock_coordinator
) -> None:
    """Test successful setup of entry."""
    mock_yolink_client.get_devices.return_value = [mock_device]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yolink_local.LocalHubMessageListener"
    ) as mock_listener:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None

    client, coordinators = entry.runtime_data
    assert client == mock_yolink_client
    assert "device_123" in coordinators

    mock_yolink_client.async_setup.assert_called_once()
    mock_listener.assert_called_once_with(hass, entry)
    mock_coordinator.assert_called_once()
    mock_coordinator.return_value.async_config_entry_first_refresh.assert_called_once()


async def test_async_setup_entry_with_paired_devices(
    hass: HomeAssistant, mock_yolink_client, mock_paired_devices, mock_coordinator
) -> None:
    """Test setup with paired devices."""
    parent, child = mock_paired_devices
    mock_yolink_client.get_devices.return_value = [parent, child]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Verify both coordinators were created
    assert mock_coordinator.call_count == 2

    # Verify parent coordinator was created with paired device
    calls = mock_coordinator.call_args_list
    # First call should be for parent device
    assert calls[0][0][2] == parent  # device parameter
    assert calls[0][0][3] == child  # paired_device parameter

    # Second call should be for child device
    assert calls[1][0][2] == child
    assert calls[1][0][3] is None


async def test_async_setup_entry_auth_failure(
    hass: HomeAssistant, mock_yolink_client
) -> None:
    """Test setup fails with authentication error."""
    mock_yolink_client.async_setup.side_effect = YoLinkAuthFailError(
        code="10001", desc="Auth failed"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_client_error(
    hass: HomeAssistant, mock_yolink_client
) -> None:
    """Test setup fails with client error."""
    mock_yolink_client.async_setup.side_effect = YoLinkClientError(
        code="10002", desc="Client error"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_timeout(
    hass: HomeAssistant, mock_yolink_client
) -> None:
    """Test setup fails with timeout."""

    async def slow_setup(*args, **kwargs):
        await asyncio.sleep(15)

    mock_yolink_client.async_setup.side_effect = slow_setup

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_coordinator_not_ready(
    hass: HomeAssistant, mock_yolink_client, mock_device, mock_coordinator
) -> None:
    """Test setup continues when coordinator first refresh fails."""
    mock_yolink_client.get_devices.return_value = [mock_device]
    mock_coordinator.return_value.async_config_entry_first_refresh.side_effect = (
        ConfigEntryNotReady("Not ready")
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Setup should still succeed with empty coordinator data
    assert entry.state is ConfigEntryState.LOADED
    assert mock_coordinator.return_value.data == {}


async def test_async_unload_entry_success(
    hass: HomeAssistant, mock_yolink_client, mock_device, mock_coordinator
) -> None:
    """Test successful unload of entry."""
    mock_yolink_client.get_devices.return_value = [mock_device]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Unload the entry
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_yolink_client.async_unload.assert_called_once()


async def test_async_unload_entry_without_runtime_data(
    hass: HomeAssistant, mock_yolink_client, mock_device, mock_coordinator
) -> None:
    """Test unload when runtime_data is None."""
    mock_yolink_client.get_devices.return_value = [mock_device]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Manually set runtime_data to None to simulate the edge case
    entry.runtime_data = None

    # Should still be able to unload without error
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # async_unload should not be called when runtime_data is None
    mock_yolink_client.async_unload.assert_not_called()
