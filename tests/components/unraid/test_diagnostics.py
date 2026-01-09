"""Tests for Unraid diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from homeassistant.components.unraid.diagnostics import (
    async_get_config_entry_diagnostics,
)


@dataclass
class MockRuntimeData:
    """Mock runtime data for testing."""

    api_client: MagicMock
    system_coordinator: MagicMock
    storage_coordinator: MagicMock
    server_info: dict


@pytest.fixture
def mock_hass():
    """Provide a mock HomeAssistant instance."""
    return MagicMock()


@pytest.fixture
def mock_coordinator():
    """Provide a mock coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.last_update_success_time = datetime(2025, 12, 23, 10, 30, 0)
    return coordinator


@pytest.fixture
def mock_config_entry(mock_coordinator):
    """Provide a mock config entry with runtime_data."""
    entry = MagicMock()
    entry.entry_id = "test-entry-123"
    entry.title = "Unraid Tower"
    entry.version = 1
    entry.runtime_data = MockRuntimeData(
        api_client=MagicMock(),
        system_coordinator=mock_coordinator,
        storage_coordinator=mock_coordinator,
        server_info={
            "uuid": "abc-123-def-456",
            "name": "tower",
            "manufacturer": "Supermicro",
            "model": "X11SSH-F",
            "sw_version": "7.2.0",
            "api_version": "4.29.2",
            "license_type": "Pro",
        },
    )
    return entry


@pytest.mark.asyncio
async def test_diagnostics_with_full_data(mock_hass, mock_config_entry) -> None:
    """Test diagnostics returns complete data when all info available."""
    result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

    assert result["entry_id"] == "test-entry-123"
    assert result["title"] == "Unraid Tower"
    assert result["version"] == 1
    assert result["server_info"]["uuid"] == "abc-123-def-456"
    assert result["server_info"]["hostname"] == "tower"
    assert result["server_info"]["manufacturer"] == "Supermicro"
    assert result["server_info"]["model"] == "X11SSH-F"
    assert result["server_info"]["sw_version"] == "7.2.0"
    assert result["server_info"]["api_version"] == "4.29.2"
    assert result["server_info"]["license_type"] == "Pro"
    assert result["system_coordinator"]["last_update_success"] is True
    assert result["storage_coordinator"]["last_update_success"] is True


@pytest.mark.asyncio
async def test_diagnostics_with_missing_server_info(
    mock_hass, mock_coordinator
) -> None:
    """Test diagnostics handles missing server info gracefully."""
    entry = MagicMock()
    entry.entry_id = "test-entry-123"
    entry.title = "Unraid Tower"
    entry.version = 1
    entry.runtime_data = MockRuntimeData(
        api_client=MagicMock(),
        system_coordinator=mock_coordinator,
        storage_coordinator=mock_coordinator,
        server_info={},  # Empty server info
    )

    result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["entry_id"] == "test-entry-123"
    assert result["title"] == "Unraid Tower"
    assert result["server_info"]["uuid"] is None
    assert result["server_info"]["hostname"] is None
    assert result["server_info"]["manufacturer"] is None
    assert result["server_info"]["model"] is None


@pytest.mark.asyncio
async def test_diagnostics_with_failed_coordinator(mock_hass) -> None:
    """Test diagnostics shows coordinator failure status."""
    failed_coordinator = MagicMock()
    failed_coordinator.last_update_success = False
    failed_coordinator.last_update_success_time = datetime(2025, 12, 23, 10, 25, 0)

    entry = MagicMock()
    entry.entry_id = "test-entry-123"
    entry.title = "Unraid Tower"
    entry.version = 1
    entry.runtime_data = MockRuntimeData(
        api_client=MagicMock(),
        system_coordinator=failed_coordinator,
        storage_coordinator=failed_coordinator,
        server_info={},
    )

    result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["system_coordinator"]["last_update_success"] is False
    assert result["storage_coordinator"]["last_update_success"] is False


@pytest.mark.asyncio
async def test_diagnostics_with_empty_server_info(mock_hass, mock_coordinator) -> None:
    """Test diagnostics when server info is empty dict."""
    entry = MagicMock()
    entry.entry_id = "test-entry-123"
    entry.title = "Unraid Tower"
    entry.version = 1
    entry.runtime_data = MockRuntimeData(
        api_client=MagicMock(),
        system_coordinator=mock_coordinator,
        storage_coordinator=mock_coordinator,
        server_info={},
    )

    result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["entry_id"] == "test-entry-123"
    assert result["server_info"]["uuid"] is None


@pytest.mark.asyncio
async def test_diagnostics_with_partial_server_info(
    mock_hass, mock_coordinator
) -> None:
    """Test diagnostics with incomplete server information."""
    entry = MagicMock()
    entry.entry_id = "test-entry-123"
    entry.title = "Unraid Tower"
    entry.version = 1
    entry.runtime_data = MockRuntimeData(
        api_client=MagicMock(),
        system_coordinator=mock_coordinator,
        storage_coordinator=mock_coordinator,
        server_info={
            "uuid": "test-uuid",
            # Missing other fields
        },
    )

    result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["server_info"]["uuid"] == "test-uuid"
    assert result["server_info"]["hostname"] is None
    assert result["server_info"]["manufacturer"] is None
    assert result["server_info"]["model"] is None


@pytest.mark.asyncio
async def test_diagnostics_does_not_expose_sensitive_data(
    mock_hass, mock_config_entry
) -> None:
    """Test diagnostics output contains no sensitive information."""
    # runtime_data already set in mock_config_entry fixture

    result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

    # Verify sensitive keys are not present
    assert "api_client" not in result
    assert "api_key" not in str(result)
    assert "password" not in str(result)
    assert "token" not in str(result)

    # Verify only expected keys exist
    assert set(result.keys()) == {
        "entry_id",
        "title",
        "version",
        "server_info",
        "system_coordinator",
        "storage_coordinator",
    }
