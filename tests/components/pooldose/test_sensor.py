"""Test the Pooldose sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.sensor import PooldoseSensor


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = ("SUCCESS", {"pool_temp_ist": [22.5, "°C"]})
    return coordinator


@pytest.fixture
def mock_client():
    """Create a mock API client."""
    return MagicMock()


def test_sensor_native_value(mock_coordinator, mock_client) -> None:
    """Test that the sensor returns the correct value."""
    sensor = PooldoseSensor(
        mock_coordinator,  # coordinator
        mock_client,  # client
        "pool_temp_ist",  # translation_key
        "pool_temp_ist",  # key
        None,  # unit
        None,  # sensor device class
        "SN123456789",  # serialnumber
        None,  # entity_category
        {},  # device_info_dict
        True,  # enabled_by_default
    )

    assert sensor.native_value == 22.5


def test_sensor_native_value_missing(mock_coordinator, mock_client) -> None:
    """Test that the sensor returns None if value is missing."""
    coordinator_no_data = MagicMock(spec=PooldoseCoordinator)
    coordinator_no_data.data = ("SUCCESS", {})

    sensor = PooldoseSensor(
        coordinator_no_data,  # coordinator
        mock_client,  # client
        "ph",  # translation_key
        "ph",  # key
        None,  # unit
        None,  # sensor device class
        "SN123456789",  # serialnumber
        None,  # entity_category
        {},  # device_info_dict
        True,  # enabled_by_default
    )

    assert sensor.native_value is None


def test_sensor_unique_id_and_name(mock_coordinator, mock_client) -> None:
    """Test unique_id and name properties."""
    sensor = PooldoseSensor(
        mock_coordinator,  # coordinator
        mock_client,  # client
        "pool_ph_ist",  # translation_key
        "PDPR1H1HAW100_FW539187_pool_ph_ist",  # key
        None,  # unit
        None,  # sensor device class
        "SN123456789",  # serialnumber
        None,  # entity_category
        {},  # device_info_dict
        True,  # enabled_by_default
    )

    assert sensor.unique_id == "SN123456789_PDPR1H1HAW100_FW539187_pool_ph_ist"
    assert hasattr(sensor, "translation_key")
