"""Test Script for Fluss Entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fluss_api import FlussApiClientCommunicationError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fluss.entity import FlussEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .conftest import mock_coordinator


@pytest.fixture
def mock_entity_description() -> EntityDescription:
    """Mock entity description."""
    return EntityDescription(key="test_key", name="Test Entity")


@pytest.mark.asyncio
async def test_fluss_entity_init(
    hass: HomeAssistant,
    mock_coordinator: DataUpdateCoordinator[dict[str, Any]],
    mock_entity_description: EntityDescription,
    snapshot: SnapshotAssertion,
) -> None:
    """Test entity initialization."""
    device: dict[str, Any] = {"deviceId": "1", "deviceName": "Test Device"}
    entity = FlussEntity(mock_coordinator, "1", device)

    assert entity.unique_id == "1"
    assert entity.device_info == snapshot
    assert entity.device == device


@pytest.mark.asyncio
async def test_fluss_entity_async_update_success(
    hass: HomeAssistant,
    mock_coordinator: DataUpdateCoordinator[dict[str, Any]],
    mock_entity_description: EntityDescription,
) -> None:
    """Test successful async update."""
    device: dict[str, Any] = {"deviceId": "1", "deviceName": "Test Device"}
    entity = FlussEntity(mock_coordinator, "1", device)

    with patch.object(mock_coordinator, "async_request_refresh") as mock_refresh:
        await entity.async_update()
        mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_fluss_entity_async_update_error(
    hass: HomeAssistant,
    mock_coordinator: DataUpdateCoordinator[dict[str, Any]],
    mock_entity_description: EntityDescription,
) -> None:
    """Test async update with communication error."""
    device: dict[str, Any] = {"deviceId": "1", "deviceName": "Test Device"}
    entity = FlussEntity(mock_coordinator, "1", device)

    with patch.object(
        mock_coordinator, "async_request_refresh", side_effect=FlussApiClientCommunicationError
    ), patch("homeassistant.components.fluss.entity.LOGGER.error") as mock_logger:
        await entity.async_update()
        mock_logger.assert_called_once()