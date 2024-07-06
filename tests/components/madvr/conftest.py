"""MadVR conftest for shared testing setup."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONFIG_ENTRY, MOCK_CONFIG, MOCK_MAC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.madvr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_madvr_client() -> Generator[AsyncMock, None, None]:
    """Mock a MadVR client."""
    with patch(
        "homeassistant.components.madvr.config_flow.Madvr", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.host = MOCK_CONFIG[CONF_HOST]
        client.port = MOCK_CONFIG[CONF_PORT]
        client.mac_address = MOCK_MAC
        client.connected = MagicMock(return_value=True)
        client.open_connection = AsyncMock()
        client._reconnect = AsyncMock()
        client.close_connection = AsyncMock()
        client.async_add_tasks = AsyncMock()
        client.async_cancel_tasks = AsyncMock()
        client.is_device_connectable = AsyncMock(return_value=True)
        client.send_command = AsyncMock()
        client.stop = MagicMock()
        client.power_on = AsyncMock()
        client.power_off = AsyncMock()
        client.add_command_to_queue = AsyncMock()
        with patch("madvr.madvr.send_magic_packet", return_value=True):
            yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return CONFIG_ENTRY


@pytest.fixture
def mock_coordinator(mock_madvr_client) -> Generator[AsyncMock, None, None]:
    """Mock a MadVRCoordinator."""
    with patch(
        "homeassistant.components.madvr.MadVRCoordinator",
        return_value=AsyncMock(),
    ) as mock_coordinator:
        mock_coordinator_instance = mock_coordinator.return_value
        mock_coordinator_instance.client = mock_madvr_client
        mock_coordinator_instance.mac = MOCK_MAC
        yield mock_coordinator_instance
