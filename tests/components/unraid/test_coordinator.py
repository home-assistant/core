"""Coordinator tests for the Unraid integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from unraid_api.exceptions import (
    UnraidAPIError,
    UnraidAuthenticationError,
    UnraidConnectionError,
)
from unraid_api.models import ServerInfo, SystemMetrics

from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.coordinator import (
    UnraidSystemCoordinator,
    UnraidSystemData,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api_client():
    """Create a mock API client with typed methods."""
    client = MagicMock()
    client.get_system_metrics = AsyncMock()
    return client


@pytest.fixture
def mock_server_info() -> ServerInfo:
    """Create a mock ServerInfo object."""
    return ServerInfo(
        uuid="test-uuid-1234",
        hostname="tower",
        manufacturer="Unraid",
        model="Server Pro",
        serial_number="ABC123",
        sw_version="7.2.0",
        hw_version="1.0",
        local_url="http://192.168.1.100",
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide a mock config entry for coordinator tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-uuid-1234",
        data={
            "host": "192.168.1.100",
            "port": 80,
            "username": "root",
            "password": "test",
        },
        title="Test Server",
    )


async def test_system_coordinator_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
) -> None:
    """Test UnraidSystemCoordinator initializes with 30s interval."""
    coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api_client=mock_api_client,
        server_info=mock_server_info,
    )

    assert coordinator.name == "tower System"
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_system_coordinator_fetch_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
) -> None:
    """Test system coordinator successfully fetches data."""
    mock_api_client.get_system_metrics.return_value = SystemMetrics(
        cpu_percent=25.5,
        cpu_temperature=45.0,
        memory_total=17179869184,
        memory_used=8589934592,
        memory_percent=50.0,
        uptime=datetime(2025, 12, 23, 10, 30, 0, tzinfo=UTC),
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, mock_server_info
    )
    data = await coordinator._async_update_data()

    assert data is not None
    assert isinstance(data, UnraidSystemData)
    assert data.metrics.cpu_percent == 25.5
    assert data.metrics.cpu_temperature == 45.0
    assert data.metrics.memory_percent == 50.0


async def test_system_coordinator_handles_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
) -> None:
    """Test system coordinator raises UpdateFailed on connection error."""
    mock_api_client.get_system_metrics.side_effect = UnraidConnectionError(
        "Connection refused"
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, mock_server_info
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "Connection error" in str(exc_info.value)


async def test_system_coordinator_handles_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
) -> None:
    """Test system coordinator raises UpdateFailed on auth error."""
    mock_api_client.get_system_metrics.side_effect = UnraidAuthenticationError(
        "Invalid credentials"
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, mock_server_info
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "Authentication failed" in str(exc_info.value)


async def test_system_coordinator_handles_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
) -> None:
    """Test system coordinator raises UpdateFailed on API error."""
    mock_api_client.get_system_metrics.side_effect = UnraidAPIError("API error")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, mock_server_info
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "API error" in str(exc_info.value)
