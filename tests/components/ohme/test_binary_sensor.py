"""Tests for binary sensors."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.ohme.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    OhmeBinarySensor,
)
from homeassistant.components.ohme.coordinator import OhmeApiResponse
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@pytest.fixture
def mock_coordinator():
    """Fixture for creating a mock coordinator."""
    return MagicMock(spec=DataUpdateCoordinator)


def test_connected_binary_sensor(mock_coordinator) -> None:
    """Test ConnectedBinarySensor."""
    description = next(
        desc for desc in BINARY_SENSOR_DESCRIPTIONS if desc.key == "car_connected"
    )
    sensor = OhmeBinarySensor(mock_coordinator, AsyncMock(), MagicMock(), description)

    mock_coordinator.data = OhmeApiResponse({"mode": "CONNECTED"}, {})
    assert sensor.is_on is True

    mock_coordinator.data = OhmeApiResponse({"mode": "DISCONNECTED"}, {})
    assert sensor.is_on is False


def test_charging_binary_sensor(mock_coordinator) -> None:
    """Test ChargingBinarySensor."""
    description = next(
        desc for desc in BINARY_SENSOR_DESCRIPTIONS if desc.key == "car_charging"
    )
    sensor = OhmeBinarySensor(mock_coordinator, AsyncMock(), MagicMock(), description)

    mock_coordinator.data = OhmeApiResponse({"power": {"watt": 100}}, {})
    assert sensor.is_on is True

    mock_coordinator.data = OhmeApiResponse({"power": {"watt": 0}}, {})
    assert sensor.is_on is False


def test_pending_approval_binary_sensor(mock_coordinator) -> None:
    """Test PendingApprovalBinarySensor."""
    description = next(
        desc for desc in BINARY_SENSOR_DESCRIPTIONS if desc.key == "pending_approval"
    )
    sensor = OhmeBinarySensor(mock_coordinator, AsyncMock(), MagicMock(), description)

    mock_coordinator.data = OhmeApiResponse({"mode": "PENDING_APPROVAL"}, {})
    assert sensor.is_on is True

    mock_coordinator.data = OhmeApiResponse({"mode": "CONNECTED"}, {})
    assert sensor.is_on is False


def test_charger_online_binary_sensor(mock_coordinator) -> None:
    """Test ChargerOnlineBinarySensor."""
    description = next(
        desc for desc in BINARY_SENSOR_DESCRIPTIONS if desc.key == "charger_online"
    )
    sensor = OhmeBinarySensor(mock_coordinator, AsyncMock(), MagicMock(), description)

    mock_coordinator.data = OhmeApiResponse({}, {"online": True})
    assert sensor.is_on is True

    mock_coordinator.data = OhmeApiResponse({}, {"online": False})
    assert sensor.is_on is False
