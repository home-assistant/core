"""Tests for the YoLink Local integration."""

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry

CONF_NET_ID: str = "net_id"
DOMAIN: str = "yolink_local"


# Test data
TEST_HOST: str = "192.168.1.100"
TEST_NET_ID: str = "test_net_id_123"
TEST_CLIENT_ID: str = "test_client_id"
TEST_CLIENT_SECRET: str = "test_client_secret"

TEST_CONFIG_DATA: dict[str, str] = {
    CONF_HOST: TEST_HOST,
    CONF_NET_ID: TEST_NET_ID,
    CONF_CLIENT_ID: TEST_CLIENT_ID,
    CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
}


@pytest.fixture
def mock_yolink_client() -> Generator[Mock]:
    """Mock YoLinkLocalHubClient."""
    with patch(
        "homeassistant.components.yolink_local.YoLinkLocalHubClient"
    ) as mock_client_class:
        client: Mock = Mock()
        client.async_setup = AsyncMock()
        client.get_devices = Mock(return_value=[])
        client.async_unload = AsyncMock()
        mock_client_class.return_value = client
        yield client


@pytest.fixture
def mock_device() -> Mock:
    """Create a mock YoLink device."""
    device: Mock = Mock(spec=YoLinkDevice)
    device.device_id = "device_123"
    device.device_type = "DoorSensor"
    device.name = "Test Door Sensor"
    return device


@pytest.fixture
def mock_coordinator() -> Generator[MagicMock]:
    """Mock YoLinkLocalCoordinator."""
    with patch(
        "homeassistant.components.yolink_local.YoLinkLocalCoordinator"
    ) as mock_coord_class:
        coordinator: Mock = Mock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = {}
        mock_coord_class.return_value = coordinator
        yield mock_coord_class


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_yolink_client: Mock,
    mock_device: Mock,
    mock_coordinator: MagicMock,
) -> None:
    """Test successful setup of entry."""
    mock_yolink_client.get_devices.return_value = [mock_device]

    entry: MockConfigEntry = MockConfigEntry(
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

    client: Any
    coordinators: dict[str, Any]
    client: Any = entry.runtime_data.client
    coordinators: dict[str, Any] = entry.runtime_data.coordinators
    assert client == mock_yolink_client
    assert "device_123" in coordinators

    mock_yolink_client.async_setup.assert_called_once()
    mock_listener.assert_called_once_with(hass, entry)
    mock_coordinator.assert_called_once()
    mock_coordinator.return_value.async_config_entry_first_refresh.assert_called_once()


async def test_async_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_yolink_client: Mock,
) -> None:
    """Test setup fails with authentication error."""
    mock_yolink_client.async_setup.side_effect = YoLinkAuthFailError(
        code="10001", desc="Auth failed"
    )

    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        result: bool = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_client_error(
    hass: HomeAssistant,
    mock_yolink_client: Mock,
) -> None:
    """Test setup fails with client error."""
    mock_yolink_client.async_setup.side_effect = YoLinkClientError(
        code="10002", desc="Client error"
    )

    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        result: bool = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_timeout(
    hass: HomeAssistant,
    mock_yolink_client: Mock,
) -> None:
    """Test setup fails with timeout."""
    mock_yolink_client.async_setup.side_effect = asyncio.TimeoutError

    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_DATA,
        unique_id=TEST_NET_ID,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.yolink_local.LocalHubMessageListener"):
        result: bool = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_coordinator_not_ready(
    hass: HomeAssistant,
    mock_yolink_client: Mock,
    mock_device: Mock,
    mock_coordinator: MagicMock,
) -> None:
    """Test setup continues when coordinator first refresh fails."""
    mock_yolink_client.get_devices.return_value = [mock_device]
    mock_coordinator.return_value.async_config_entry_first_refresh.side_effect = (
        ConfigEntryNotReady("Not ready")
    )

    entry: MockConfigEntry = MockConfigEntry(
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
    hass: HomeAssistant,
    mock_yolink_client: Mock,
    mock_device: Mock,
    mock_coordinator: MagicMock,
) -> None:
    """Test successful unload of entry."""
    mock_yolink_client.get_devices.return_value = [mock_device]

    entry: MockConfigEntry = MockConfigEntry(
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
    hass: HomeAssistant,
    mock_yolink_client: Mock,
    mock_device: Mock,
    mock_coordinator: MagicMock,
) -> None:
    """Test unload when runtime_data is None."""
    mock_yolink_client.get_devices.return_value = [mock_device]

    entry: MockConfigEntry = MockConfigEntry(
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
