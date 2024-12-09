"""Tests for binary sensors."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.ohme.binary_sensor import (
    ChargerOnlineBinarySensor,
    ChargingBinarySensor,
    ConnectedBinarySensor,
    PendingApprovalBinarySensor,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@pytest.fixture
def mock_coordinator():
    """Fixture for creating a mock coordinator."""
    return MagicMock(spec=DataUpdateCoordinator)


def test_connected_binary_sensor(mock_coordinator) -> None:
    """Test ConnectedBinarySensor."""
    sensor = ConnectedBinarySensor(mock_coordinator, AsyncMock(), MagicMock())
    mock_coordinator.data = {"mode": "CONNECTED"}
    assert sensor.is_on is True

    mock_coordinator.data = {"mode": "DISCONNECTED"}
    assert sensor.is_on is False


def test_charging_binary_sensor(mock_coordinator) -> None:
    """Test ChargingBinarySensor."""
    sensor = ChargingBinarySensor(mock_coordinator, AsyncMock(), MagicMock())
    mock_coordinator.data = {
        "power": {"watt": 100},
        "batterySoc": {"wh": 50},
        "mode": "CONNECTED",
        "allSessionSlots": [],
    }
    assert sensor.is_on is True


def test_pending_approval_binary_sensor(mock_coordinator) -> None:
    """Test PendingApprovalBinarySensor."""
    sensor = PendingApprovalBinarySensor(mock_coordinator, AsyncMock(), MagicMock())
    mock_coordinator.data = {"mode": "PENDING_APPROVAL"}
    assert sensor.is_on is True

    mock_coordinator.data = {"mode": "CONNECTED"}
    assert sensor.is_on is False


def test_charger_online_binary_sensor(mock_coordinator) -> None:
    """Test ChargerOnlineBinarySensor."""
    sensor = ChargerOnlineBinarySensor(mock_coordinator, AsyncMock(), MagicMock())
    mock_coordinator.data = {"online": True}
    assert sensor.is_on is True

    mock_coordinator.data = {"online": False}
    assert sensor.is_on is False
