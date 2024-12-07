"""Tests for binary sensors."""

import pytest
from unittest.mock import MagicMock
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from custom_components.ohme.const import (
    DOMAIN,
    DATA_CLIENT,
    DATA_COORDINATORS,
    COORDINATOR_CHARGESESSIONS,
    COORDINATOR_ADVANCED,
)

from custom_components.ohme.binary_sensor import (
    ConnectedBinarySensor,
    ChargingBinarySensor,
    PendingApprovalBinarySensor,
    ChargerOnlineBinarySensor,
)


@pytest.fixture
def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            "test_account": {
                DATA_CLIENT: MagicMock(),
                DATA_COORDINATORS: {
                    COORDINATOR_CHARGESESSIONS: MagicMock(spec=DataUpdateCoordinator),
                    COORDINATOR_ADVANCED: MagicMock(spec=DataUpdateCoordinator),
                },
            }
        }
    }
    return hass


@pytest.fixture
def mock_coordinator():
    """Fixture for creating a mock coordinator."""
    return MagicMock(spec=DataUpdateCoordinator)


@pytest.fixture
def mock_client():
    """Fixture for creating a mock client."""
    mock = MagicMock()
    mock.email = "test_account"
    return mock


def test_connected_binary_sensor(mock_hass, mock_coordinator, mock_client):
    """Test ConnectedBinarySensor."""
    sensor = ConnectedBinarySensor(mock_coordinator, mock_hass, mock_client)
    mock_coordinator.data = {"mode": "CONNECTED"}
    assert sensor.is_on is True

    mock_coordinator.data = {"mode": "DISCONNECTED"}
    assert sensor.is_on is False


def test_charging_binary_sensor(mock_hass, mock_coordinator, mock_client):
    """Test ChargingBinarySensor."""
    sensor = ChargingBinarySensor(mock_coordinator, mock_hass, mock_client)
    mock_coordinator.data = {
        "power": {"watt": 100},
        "batterySoc": {"wh": 50},
        "mode": "CONNECTED",
        "allSessionSlots": [],
    }
    sensor._last_reading = {"power": {"watt": 100}, "batterySoc": {"wh": 40}}
    assert sensor._calculate_state() is True


def test_pending_approval_binary_sensor(mock_hass, mock_coordinator, mock_client):
    """Test PendingApprovalBinarySensor."""
    sensor = PendingApprovalBinarySensor(mock_coordinator, mock_hass, mock_client)
    mock_coordinator.data = {"mode": "PENDING_APPROVAL"}
    assert sensor.is_on is True

    mock_coordinator.data = {"mode": "CONNECTED"}
    assert sensor.is_on is False


def test_charger_online_binary_sensor(mock_hass, mock_coordinator, mock_client):
    """Test ChargerOnlineBinarySensor."""
    sensor = ChargerOnlineBinarySensor(mock_coordinator, mock_hass, mock_client)
    mock_coordinator.data = {"online": True}
    assert sensor.is_on is True

    mock_coordinator.data = {"online": False}
    assert sensor.is_on is False
