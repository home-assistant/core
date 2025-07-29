"""Test the AirPatrol data update coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.airpatrol.api import AirPatrolAPI
from homeassistant.components.airpatrol.coordinator import (
    SCAN_INTERVAL,
    AirPatrolDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_api():
    """Mock AirPatrol API."""
    api = MagicMock(spec=AirPatrolAPI)
    api.get_data.return_value = []
    return api


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {"email": "test@example.com"}
    return entry


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_api, mock_config_entry):
    """Create coordinator instance."""
    return AirPatrolDataUpdateCoordinator(hass, mock_api, mock_config_entry)


def test_coordinator_initialization(coordinator) -> None:
    """Test coordinator initialization."""
    assert coordinator.api is not None
    assert coordinator.config_entry is not None
    assert coordinator.name == "AirPatrol test@example.com"


async def test_async_update_data_success(coordinator) -> None:
    """Test successful data update."""
    result = await coordinator._async_update_data()

    assert result == []
    coordinator.api.get_data.assert_called_once()


async def test_async_update_data_failure(coordinator) -> None:
    """Test data update failure."""
    coordinator.api.get_data = AsyncMock(side_effect=Exception("API Error"))

    with pytest.raises(UpdateFailed, match="Error communicating with AirPatrol"):
        await coordinator._async_update_data()


def test_coordinator_update_interval(coordinator) -> None:
    """Test coordinator update interval."""
    assert coordinator.update_interval == SCAN_INTERVAL
    assert isinstance(SCAN_INTERVAL, timedelta)


async def test_coordinator_with_real_hass(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """Test coordinator with real Home Assistant instance."""
    coordinator = AirPatrolDataUpdateCoordinator(hass, mock_api, mock_config_entry)

    assert coordinator.hass == hass
    assert coordinator.api == mock_api
    assert coordinator.config_entry == mock_config_entry
    assert coordinator.name == f"AirPatrol {mock_config_entry.data['email']}"
