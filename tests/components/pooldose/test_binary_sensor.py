"""Tests for the Seko Pooldose binary sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.pooldose.binary_sensor import PooldoseBinarySensor
from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.pooldose_api import PooldoseAPIClient


@pytest.fixture
def mock_api():
    """Fixture for a mocked PooldoseAPIClient."""
    api = MagicMock(spec=PooldoseAPIClient)
    api.serial_key = "PDPR1H1HAW100_FW539187"
    return api


@pytest.fixture
def mock_coordinator():
    """Fixture for a mocked PooldoseCoordinator."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "devicedata": {
            "PDPR1H1HAW100_FW539187": {
                "PDPR1H1HAW100_FW539187_alarm": {"current": "F"},
                "PDPR1H1HAW100_FW539187_error": {"current": "O"},
            }
        }
    }
    return coordinator


def test_binary_sensor_is_on(mock_coordinator, mock_api) -> None:
    """Test that the binary sensor returns True when on."""
    sensor = PooldoseBinarySensor(
        mock_coordinator,
        mock_api,
        "Alarm",
        "pooldose_alarm",
        "PDPR1H1HAW100_FW539187_alarm",
        "PDPR1H1HAW100_FW539187",  # serialnumber
        None,  # entity_category
        None,  # device_class
        {},  # device_info_dict
        True,  # enabled_by_default
    )
    assert sensor.is_on is True


def test_binary_sensor_is_off(mock_coordinator, mock_api) -> None:
    """Test that the binary sensor returns False when off."""
    sensor = PooldoseBinarySensor(
        mock_coordinator,
        mock_api,
        "Error",
        "pooldose_error",
        "PDPR1H1HAW100_FW539187_error",
        "PDPR1H1HAW100_FW539187",
        None,
        None,
        {},
        True,
    )
    assert sensor.is_on is False


def test_binary_sensor_is_none(mock_coordinator, mock_api) -> None:
    """Test that the binary sensor returns None if value is missing."""
    sensor = PooldoseBinarySensor(
        mock_coordinator,
        mock_api,
        "Unknown",
        "pooldose_unknown",
        "PDPR1H1HAW100_FW539187_unknown",
        "PDPR1H1HAW100_FW539187",
        None,
        None,
        {},
        True,
    )
    assert sensor.is_on is None
