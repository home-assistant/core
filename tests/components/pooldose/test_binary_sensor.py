"""Tests for the Seko Pooldose binary sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.pooldose.binary_sensor import PooldoseBinarySensor


@pytest.fixture
def mock_coordinator():
    """Fixture for a mocked coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "devicedata": {
            "PDPR1H1HAW100_FW539187": {
                "pump_status": {"current": True},
            }
        }
    }
    return coordinator


@pytest.fixture
def mock_api():
    """Fixture for a mocked API."""
    api = MagicMock()
    api.serial_key = "PDPR1H1HAW100_FW539187"
    return api


def test_binary_sensor_is_on(mock_coordinator, mock_api) -> None:
    """Test that the binary sensor is on."""
    sensor = PooldoseBinarySensor(
        mock_coordinator, mock_api, "Pump Status", "pump_status", "pump_status"
    )
    assert sensor.is_on["current"] is True


def test_binary_sensor_is_off(mock_coordinator, mock_api) -> None:
    """Test that the binary sensor is off if value is missing."""
    sensor = PooldoseBinarySensor(
        mock_coordinator, mock_api, "Pump Status", "pump_status", "invalid_key"
    )
    assert sensor.is_on is None
