"""Test the Pooldose sensor platform."""

from unittest.mock import MagicMock, patch

from pooldose.request_handler import RequestStatus
import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.sensor import (
    PooldoseSensor,
    PooldoseStaticSensor,
)


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
    """Create a mock coordinator for static sensors."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = (
        RequestStatus.SUCCESS,
        {},
    )  # Static sensors don't use coordinator data
    return coordinator


@pytest.fixture
def mock_client():
    """Create a mock API client."""
    return MagicMock()


@pytest.fixture
def mock_device_info():
    """Create mock device info dict."""
    return {
        "SERIAL_NUMBER": "SN123456789",
        "API_VERSION": "v1.0",
        "FW_VERSION": "1.2.3",
        "MODEL": "PoolDose Pro",
    }


def test_dynamic_sensor_native_value(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test that the dynamic sensor returns the correct value."""
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        "temperature",  # translation_key
        "temperature",  # key
        None,  # unit (will be determined from data)
        None,  # device_class
        "SN123456789",  # serialnumber
        None,  # entity_category
        mock_device_info,  # device_info_dict
        True,  # enabled_by_default
    )

    assert sensor.native_value == 25.5
    assert sensor.native_unit_of_measurement == "°C"


def test_dynamic_sensor_native_value_missing_key(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test that the sensor returns None if key is missing."""
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        "missing_sensor",  # translation_key
        "missing_sensor",  # key - not in coordinator data
        None,
        None,
        "SN123456789",
        None,
        mock_device_info,
        True,
    )

    assert sensor.native_value is None


def test_dynamic_sensor_api_error(mock_client, mock_device_info) -> None:
    """Test that the sensor returns None when API returns error."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = (RequestStatus.HOST_UNREACHABLE, {})

    sensor = PooldoseSensor(
        coordinator,
        mock_client,
        "temperature",
        "temperature",
        None,
        None,
        "SN123456789",
        None,
        mock_device_info,
        True,
    )

    assert sensor.native_value is None


def test_static_sensor_native_value(
    mock_static_coordinator, mock_client, mock_device_info
) -> None:
    """Test that the static sensor returns the correct value from device info."""
    sensor = PooldoseStaticSensor(
        mock_static_coordinator,
        mock_client,
        "api_version",  # translation_key
        "API_VERSION",  # key
        None,  # device_class
        "SN123456789",  # serialnumber
        None,  # entity_category
        mock_device_info,  # device_info_dict
        True,  # enabled_by_default
    )

    assert sensor.native_value == "v1.0"


def test_static_sensor_missing_key(
    mock_static_coordinator, mock_client, mock_device_info
) -> None:
    """Test that the static sensor returns None if key is missing."""
    sensor = PooldoseStaticSensor(
        mock_static_coordinator,
        mock_client,
        "missing_key",
        "MISSING_KEY",  # Not in device_info
        None,
        "SN123456789",
        None,
        mock_device_info,
        True,
    )

    assert sensor.native_value is None


def test_sensor_unique_id_and_name(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test unique_id and translation_key properties."""
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        "temperature",
        "temperature",
        None,
        None,
        "SN123456789",
        None,
        mock_device_info,
        True,
    )

    assert sensor.unique_id == "SN123456789_temperature"
    assert sensor.translation_key == "temperature"
    assert sensor.has_entity_name is True


def test_sensor_with_predefined_unit(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test sensor with predefined unit overrides API unit."""
    sensor = PooldoseSensor(
        mock_coordinator,
        mock_client,
        "temperature",
        "temperature",
        "°F",  # Predefined unit
        None,
        "SN123456789",
        None,
        mock_device_info,
        True,
    )

    # Should use predefined unit, not the one from API data
    assert sensor.native_unit_of_measurement == "°F"


def test_sensor_empty_data(mock_client, mock_device_info) -> None:
    """Test sensor behavior with empty coordinator data."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = None

    sensor = PooldoseSensor(
        coordinator,
        mock_client,
        "temperature",
        "temperature",
        None,
        None,
        "SN123456789",
        None,
        mock_device_info,
        True,
    )

    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement is None


def test_sensor_with_mapping_patched(
    mock_coordinator, mock_client, mock_device_info
) -> None:
    """Test sensor with patched DYNAMIC_SENSOR_MAP."""
    with patch(
        "homeassistant.components.pooldose.const.DYNAMIC_SENSOR_MAP",
        {"temperature": (None, None, True)},  # (device_class, entity_category, enabled)
    ):
        sensor = PooldoseSensor(
            mock_coordinator,
            mock_client,
            "temperature",
            "temperature",
            None,
            None,  # device_class from mapping
            "SN123456789",
            None,  # entity_category from mapping
            mock_device_info,
            True,
        )

        assert sensor.native_value == 25.5
        assert sensor.device_class is None  # From mapping
        assert sensor.entity_category is None  # From mapping
