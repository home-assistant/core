"""Shared pytest fixtures for Unraid integration tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from unraid_api.models import SystemMetrics

from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.coordinator import UnraidSystemData
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def make_system_data(
    cpu_percent: float | None = None,
    cpu_temperature: float | None = None,
    memory_used: int | None = None,
    memory_total: int | None = None,
    memory_percent: float | None = None,
    uptime: datetime | None = None,
) -> UnraidSystemData:
    """Create a UnraidSystemData instance for testing."""
    return UnraidSystemData(
        metrics=SystemMetrics(
            cpu_percent=cpu_percent,
            cpu_temperature=cpu_temperature,
            memory_percent=memory_percent,
            memory_total=memory_total,
            memory_used=memory_used,
            uptime=uptime,
        ),
    )


@pytest.fixture
def mock_api_client():
    """Provide a mocked Unraid API client."""
    client = MagicMock()
    client.query = AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide a mock config entry for tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-uuid-1234",
        data={
            "host": "192.168.1.100",
            "port": 80,
            "username": "root",
            "password": "test",
            "use_ssl": False,
        },
        title="Test Server",
    )


@pytest.fixture
def mock_unraid_client():
    """Return a mocked Unraid API client."""
    with patch(
        "homeassistant.components.unraid.config_flow.Unraid", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.get_server_info = AsyncMock(
            return_value=MagicMock(
                uuid="test-uuid-1234",
                version="7.0.0",
            )
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unraid_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Unraid integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.unraid.Unraid",
            return_value=mock_unraid_client,
        ),
        patch(
            "homeassistant.components.unraid.coordinator.UnraidSystemCoordinator._async_update_data",
            return_value=make_system_data(
                cpu_percent=25.5,
                cpu_temperature=45.0,
                memory_percent=50.0,
                memory_used=8_000_000,
                memory_total=16_000_000,
                uptime=datetime(2024, 1, 1, 12, 0, 0),
            ),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
