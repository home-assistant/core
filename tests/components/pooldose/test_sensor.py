"""Tests for the Seko Pooldose sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.pooldose_api import PooldoseAPIClient
from homeassistant.components.pooldose.sensor import PooldoseSensor


@pytest.fixture
def mock_api() -> PooldoseAPIClient:
    """Return a mocked PooldoseAPIClient."""
    api = MagicMock(spec=PooldoseAPIClient)
    api.serial_key = "PDPR1H1HAW100_FW539187"
    return api


@pytest.fixture
def mock_coordinator() -> PooldoseCoordinator:
    """Return a mocked PooldoseCoordinator."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "devicedata": {
            "PDPR1H1HAW100_FW539187": {
                "PDPR1H1HAW100_FW539187_w_1eommf39k": {"current": 23.5},
                "PDPR1H1HAW100_FW539187_w_1ekeigkin": {"current": 7.1},
            }
        }
    }
    return coordinator


def test_sensor_native_value(
    mock_coordinator: PooldoseCoordinator, mock_api: PooldoseAPIClient
) -> None:
    """Test that the sensor returns the correct value."""
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_api,
        "Pool Temperature Actual",
        "pool_temp_ist",
        "PDPR1H1HAW100_FW539187_w_1eommf39k",
        "°C",
        "temperature",
        "PDPR1H1HAW100_FW539187",  # serialnumber
        None,  # entity_category
        {},  # device_info_dict
        True,  # enabled_by_default
    )
    assert sensor.native_value == 23.5


def test_sensor_native_value_missing(
    mock_coordinator: PooldoseCoordinator, mock_api: PooldoseAPIClient
) -> None:
    """Test that the sensor returns None if value is missing."""
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_api,
        "Pool pH Target",
        "pool_ph_soll",
        "PDPR1H1HAW100_FW539187_w_1ekeiqfat",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187",
        None,
        {},
        True,
    )
    assert sensor.native_value is None


def test_sensor_unique_id_and_name(
    mock_coordinator: PooldoseCoordinator, mock_api: PooldoseAPIClient
) -> None:
    """Test unique_id and name properties."""
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_api,
        "Pool pH Actual",
        "pool_ph_ist",
        "PDPR1H1HAW100_FW539187_w_1ekeigkin",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187",
        None,
        {},
        True,
    )
    expected_unique_id = "PDPR1H1HAW100_FW539187_PDPR1H1HAW100_FW539187_w_1ekeigkin"
    assert sensor.unique_id == expected_unique_id
    assert sensor.translation_key == "Pool pH Actual"
