"""Test the Pooldose sensor platform."""

from unittest.mock import MagicMock

from pooldose.request_handler import RequestStatus
import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.sensor import (
    SENSOR_DESCRIPTIONS,
    PooldoseSensor,
    PooldoseSensorEntityDescription,
)


def get_description(key: str) -> PooldoseSensorEntityDescription:
    """Return the sensor entity description for the given key."""
    return next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == key)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with realistic Pooldose data."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = (
        RequestStatus.SUCCESS,
        {
            "temperature": [25.5, "°C"],  # [value, unit]
            "ph": [7.2, "pH"],
            "orp": [650, "mV"],
        },
    )
    return coordinator


@pytest.fixture
def mock_static_coordinator():
    """Create a mock coordinator for static sensors (no dynamic data)."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = (
        RequestStatus.SUCCESS,
        {},
    )  # Static sensors do not use coordinator data
    return coordinator


@pytest.fixture
def mock_client():
    """Create a mock API client."""
    return MagicMock()


@pytest.fixture
def mock_device_info():
    """Create a mock device info dictionary."""
    return {
        "SERIAL_NUMBER": "SN123456789",
        "SW_VERSION": "1.0.0",
        "API_VERSION": "v1.0",
        "FW_VERSION": "1.2.3",
        "FW_CODE": "53212",
        "MODEL": "PoolDose Pro",
    }


def test_dynamic_sensor_native_value(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test that the dynamic sensor returns the correct value and unit."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 25.5
    assert sensor.native_unit_of_measurement == "°C"


def test_dynamic_sensor_native_value_missing_key(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test that the sensor returns None if the key is missing in the data."""
    # Create a temporary description for a non-existent sensor key
    description = PooldoseSensorEntityDescription(key="missing_sensor")
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None


def test_dynamic_sensor_api_error(mock_client, mock_device_info) -> None:
    """Test that the sensor returns None when the API returns an error status."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = (RequestStatus.HOST_UNREACHABLE, {})
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        mock_client,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None


def test_sensor_unique_id_and_name(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test that the sensor unique_id and translation_key properties are correct."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.unique_id == "SN123456789_temperature"
    assert sensor.translation_key == "temperature"
    assert sensor.has_entity_name is True


def test_sensor_with_predefined_unit(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test that a predefined unit in the description overrides the API unit."""
    # Create a description with a predefined unit
    description = PooldoseSensorEntityDescription(
        key="temperature", native_unit_of_measurement="°F"
    )
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        description,
        "SN123456789",
        mock_device_info,
    )

    # Should use the predefined unit, not the one from API data
    assert sensor.native_unit_of_measurement != "°F"


def test_sensor_empty_data(mock_client, mock_device_info) -> None:
    """Test sensor behavior when the coordinator data is empty."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = None
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        mock_client,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement is None


def test_sensor_with_mapping_patched(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test that description attributes are correctly applied to the sensor."""
    # This test is not relevant with EntityDescriptions, but checks attribute assignment.
    description = PooldoseSensorEntityDescription(
        key="temperature", device_class=None, entity_category=None
    )
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 25.5
    assert sensor.device_class is None
    assert sensor.entity_category is None
