"""Tests for buttons."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.ohme.button import OhmeApproveChargeButton, async_setup_entry
from custom_components.ohme.const import (
    COORDINATOR_CHARGESESSIONS,
    DATA_CLIENT,
    DATA_COORDINATORS,
    DOMAIN,
)
import pytest


@pytest.fixture
def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_account": {}}}
    return hass


@pytest.fixture
def mock_config_entry():
    """Fixture for creating a mock config entry."""
    return AsyncMock(data={"email": "test@example.com"})


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


@pytest.fixture
def setup_hass(mock_hass, mock_config_entry, mock_client, mock_coordinator):
    """Fixture for setting up Home Assistant."""
    mock_hass.data = {
        DOMAIN: {
            "test@example.com": {
                DATA_CLIENT: mock_client,
                DATA_COORDINATORS: {COORDINATOR_CHARGESESSIONS: mock_coordinator},
            }
        }
    }
    return mock_hass


@pytest.mark.asyncio
async def test_async_setup_entry(setup_hass, mock_config_entry) -> None:
    """Test async_setup_entry."""
    async_add_entities = AsyncMock()
    await async_setup_entry(setup_hass, mock_config_entry, async_add_entities)
    assert async_add_entities.call_count == 1


@pytest.mark.asyncio
async def test_ohme_approve_charge_button(
    setup_hass, mock_client, mock_coordinator
) -> None:
    """Test OhmeApproveChargeButton."""
    button = OhmeApproveChargeButton(mock_coordinator, setup_hass, mock_client)
    await button.async_press()
    mock_client.async_approve_charge.assert_called_once()
    mock_coordinator.async_refresh.assert_called_once()
