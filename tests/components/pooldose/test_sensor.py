"""Test the Pooldose sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.sensor import (
    SENSOR_DESCRIPTIONS,
    PooldoseSensor,
    PooldoseSensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory


def get_description(key: str) -> PooldoseSensorEntityDescription:
    """Return the sensor entity description for the given key."""
    return next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == key)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with realistic Pooldose data."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": [25.5, "°C"],  # [value, unit]
        "ph": [7.2, "pH"],
        "orp": [650, "mV"],
        "ph_type_dosing": ["Automatic", ""],
        "peristaltic_ph_dosing": [15, "ml/min"],
        "ofa_ph_value": [7.0, "pH"],
        "orp_type_dosing": ["Manual", ""],
        "peristaltic_orp_dosing": [10, "ml/min"],
        "ofa_orp_value": [700, "mV"],
        "ph_calibration_type": ["2-point", ""],
        "ph_calibration_offset": [0.1, "mV"],
        "ph_calibration_slope": [58.2, "mV/pH"],
        "orp_calibration_type": ["1-point", ""],
        "orp_calibration_offset": [5.0, "mV"],
        "orp_calibration_slope": [1.0, "mV/mV"],
    }
    return coordinator


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


def test_sensor_basic_properties(mock_coordinator, mock_device_info) -> None:
    """Test that the sensor has correct basic properties."""
    description = get_description("ph")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.unique_id == "SN123456789_ph"
    assert sensor.has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.PH


def test_sensor_native_value(mock_coordinator, mock_device_info) -> None:
    """Test that the sensor returns the correct value."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 25.5


def test_sensor_temperature_unit_dynamic(mock_coordinator, mock_device_info) -> None:
    """Test that temperature sensor gets unit dynamically from API data."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_unit_of_measurement == "°C"


def test_sensor_temperature_unit_fahrenheit(mock_device_info) -> None:
    """Test that temperature sensor handles Fahrenheit unit."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": [77.0, "°F"],  # Fahrenheit temperature
    }
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 77.0
    assert sensor.native_unit_of_measurement == "°F"


def test_sensor_static_unit_orp(mock_coordinator, mock_device_info) -> None:
    """Test that ORP sensor uses static unit definition."""
    description = get_description("orp")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 650
    assert sensor.native_unit_of_measurement == "mV"  # Static unit from description


def test_sensor_static_unit_dosing(mock_coordinator, mock_device_info) -> None:
    """Test that dosing sensor uses static unit definition."""
    description = get_description("peristaltic_ph_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 15
    assert sensor.native_unit_of_measurement is None


def test_sensor_ph_no_unit(mock_coordinator, mock_device_info) -> None:
    """Test that pH sensor has no unit (dimensionless)."""
    description = get_description("ph")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 7.2
    assert sensor.native_unit_of_measurement is None


def test_sensor_native_value_missing_key(mock_coordinator, mock_device_info) -> None:
    """Test that the sensor returns None if the key is missing in the data."""
    description = PooldoseSensorEntityDescription(
        key="missing_sensor",
    )
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None


def test_diagnostic_sensor_entity_category(mock_coordinator, mock_device_info) -> None:
    """Test that diagnostic sensors have correct entity category."""
    description = get_description("ph_type_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.native_value == "Automatic"


def test_sensor_disabled_by_default(mock_coordinator, mock_device_info) -> None:
    """Test that some sensors are disabled by default."""
    description = get_description("peristaltic_ph_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.entity_registry_enabled_default is False
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC


def test_sensor_value_function(mock_coordinator, mock_device_info) -> None:
    """Test that sensor uses the value function correctly."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    # Test that value_fn extracts the first element from the data array
    assert sensor.native_value == 25.5  # First element of [25.5, "°C"]


def test_all_sensor_descriptions_have_required_fields() -> None:
    """Test that all sensor descriptions have required fields."""
    for description in SENSOR_DESCRIPTIONS:
        assert description.key is not None
        # Check that diagnostic sensors have entity_category set
        if description.entity_registry_enabled_default is False:
            assert description.entity_category == EntityCategory.DIAGNOSTIC


def test_sensor_entity_description_inheritance() -> None:
    """Test that PooldoseSensorEntityDescription properly inherits from SensorEntityDescription."""
    description = PooldoseSensorEntityDescription(
        key="test_key",
        device_class=SensorDeviceClass.TEMPERATURE,
    )

    assert description.key == "test_key"
    assert description.device_class == SensorDeviceClass.TEMPERATURE

    # Test that entity_category can be set (specific to PooldoseSensorEntityDescription)
    diagnostic_description = PooldoseSensorEntityDescription(
        key="diagnostic_sensor",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    assert diagnostic_description.entity_category == EntityCategory.DIAGNOSTIC
    assert diagnostic_description.key == "diagnostic_sensor"


def test_sensor_device_classes() -> None:
    """Test that sensors have correct device classes."""
    temperature_desc = get_description("temperature")
    assert temperature_desc.device_class == SensorDeviceClass.TEMPERATURE

    ph_desc = get_description("ph")
    assert ph_desc.device_class == SensorDeviceClass.PH

    orp_desc = get_description("orp")
    assert orp_desc.device_class == SensorDeviceClass.VOLTAGE


def test_sensor_unique_id_generation(mock_coordinator, mock_device_info) -> None:
    """Test that sensors generate correct unique IDs."""
    description = get_description("ph_calibration_offset")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.unique_id == "SN123456789_ph_calibration_offset"


def test_sensor_text_values(mock_coordinator, mock_device_info) -> None:
    """Test sensors that return text values."""
    description = get_description("ph_type_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == "Automatic"
    assert sensor.native_unit_of_measurement is None
