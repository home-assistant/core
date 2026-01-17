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

from homeassistant.components.unraid.coordinator import (
    UnraidSystemCoordinator,
    UnraidSystemData,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock API client."""
    client = MagicMock()
    client.get_system_metrics = AsyncMock()
    return client


async def test_coordinator_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
) -> None:
    """Test coordinator initializes with correct settings."""
    coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api_client=mock_api_client,
        server_info=mock_server_info,
    )

    assert coordinator.name == "tower System"
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_coordinator_fetch_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
) -> None:
    """Test coordinator successfully fetches data."""
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


@pytest.mark.parametrize(
    ("exception", "expected_exception", "expected_message"),
    [
        (UnraidConnectionError("Connection refused"), UpdateFailed, "Connection error"),
        (
            UnraidAuthenticationError("Invalid credentials"),
            ConfigEntryError,
            "Authentication failed",
        ),
        (UnraidAPIError("API error"), UpdateFailed, "API error"),
    ],
)
async def test_coordinator_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_server_info: ServerInfo,
    exception: Exception,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    """Test coordinator error handling."""
    mock_api_client.get_system_metrics.side_effect = exception

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, mock_server_info
    )

    with pytest.raises(expected_exception) as exc_info:
        await coordinator._async_update_data()

    assert expected_message in str(exc_info.value)
