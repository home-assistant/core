"""Tests for buttons."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.ohme import OhmeRuntimeData
from homeassistant.components.ohme.button import (
    OhmeApproveChargeButton,
    async_setup_entry,
)


@pytest.fixture
def mock_config_entry(mock_client, mock_coordinator):
    """Fixture for creating a mock config entry."""
    return AsyncMock(
        data={"email": "test@example.com"},
        runtime_data=OhmeRuntimeData(mock_client, [mock_coordinator * 4], []),
    )


@pytest.fixture
def mock_client():
    """Fixture for creating a mock client."""
    client = AsyncMock()
    client.is_capable.return_value = True
    client.async_approve_charge = AsyncMock()
    return client


@pytest.fixture
def mock_coordinator():
    """Fixture for creating a mock coordinator."""
    coordinator = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry(mock_config_entry) -> None:
    """Test async_setup_entry."""
    async_add_entities = AsyncMock()
    await async_setup_entry(MagicMock(), mock_config_entry, async_add_entities)
    assert async_add_entities.call_count == 1


@pytest.mark.asyncio
async def test_ohme_approve_charge_button(mock_client, mock_coordinator) -> None:
    """Test OhmeApproveChargeButton."""
    button = OhmeApproveChargeButton(mock_coordinator, MagicMock(), mock_client)
    await button.async_press()
    mock_client.async_approve_charge.assert_called_once()
    mock_coordinator.async_refresh.assert_called_once()
