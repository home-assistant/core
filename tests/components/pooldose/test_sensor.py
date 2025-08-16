"""Test the Pooldose sensor platform."""

import asyncio
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.entity import PooldoseEntity
import homeassistant.components.pooldose.sensor as sensor_module
from homeassistant.components.pooldose.sensor import (
    SENSOR_DESCRIPTIONS,
    PooldoseSensor,
    PooldoseSensorEntityDescription,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity


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


def test_sensor_empty_coordinator_data(mock_device_info) -> None:
    """Test sensor behavior when coordinator data is empty."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {}
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement is None


def test_sensor_temperature_no_unit_data(mock_device_info) -> None:
    """Test temperature sensor when unit data is missing."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": [25.5],  # Only value, no unit
    }
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 25.5
    assert sensor.native_unit_of_measurement is None


def test_sensor_temperature_invalid_data_format(mock_device_info) -> None:
    """Test temperature sensor with invalid data format."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": "invalid_format",  # String instead of list
    }
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement is None


def test_sensor_empty_list_data(mock_device_info) -> None:
    """Test sensor with empty list data."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": [],  # Empty list
    }
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement is None


def test_sensor_none_data_value(mock_device_info) -> None:
    """Test sensor when data value is None."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": None,
    }
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value is None
    assert sensor.native_unit_of_measurement is None


def test_sensor_non_temperature_unit_handling(
    mock_coordinator, mock_device_info
) -> None:
    """Test that non-temperature sensors don't use dynamic unit logic."""
    description = get_description("ph")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    # pH sensor should not use temperature unit logic
    assert sensor.native_unit_of_measurement is None


def test_sensor_static_unit_override(mock_coordinator, mock_device_info) -> None:
    """Test that static unit from description overrides dynamic logic."""
    description = get_description("orp")  # Has static mV unit
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    # Should use static unit from description, not from data
    assert sensor.native_unit_of_measurement == "mV"


def test_sensor_enum_device_class(mock_coordinator, mock_device_info) -> None:
    """Test sensor with ENUM device class."""
    description = get_description("ph_type_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.device_class == SensorDeviceClass.ENUM
    assert sensor.options == ["alcalyne", "acid"]


def test_sensor_duration_device_class(mock_coordinator, mock_device_info) -> None:
    """Test sensor with DURATION device class."""
    description = get_description("ofa_ph_value")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.device_class == SensorDeviceClass.DURATION
    assert sensor.native_unit_of_measurement == "min"


def test_sensor_voltage_device_class_with_precision(
    mock_coordinator, mock_device_info
) -> None:
    """Test sensor with VOLTAGE device class and display precision."""
    description = get_description("ph_calibration_offset")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.device_class == SensorDeviceClass.VOLTAGE
    assert sensor.suggested_display_precision == 2
    assert sensor.native_unit_of_measurement == "mV"


def test_sensor_translation_keys() -> None:
    """Test that sensors have correct translation keys."""
    orp_desc = get_description("orp")
    assert orp_desc.translation_key == "orp"

    ph_dosing_desc = get_description("ph_type_dosing")
    assert ph_dosing_desc.translation_key == "ph_type_dosing"

    # Temperature and pH don't need translation keys (use device class)
    temp_desc = get_description("temperature")
    assert temp_desc.translation_key is None

    ph_desc = get_description("ph")
    assert ph_desc.translation_key is None


def test_sensor_options_attribute() -> None:
    """Test that ENUM sensors have correct options."""
    ph_dosing_desc = get_description("ph_type_dosing")
    assert ph_dosing_desc.options == ["alcalyne", "acid"]

    orp_dosing_desc = get_description("peristaltic_orp_dosing")
    assert orp_dosing_desc.options == ["off", "proportional", "on_off", "timed"]

    # Non-enum sensors should not have options
    temp_desc = get_description("temperature")
    assert not hasattr(temp_desc, "options") or temp_desc.options is None


def test_async_setup_entry_filtering(mock_device_info) -> None:
    """Test that async_setup_entry only creates entities for available sensors."""
    # Mock the necessary objects
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MagicMock()
    config_entry.unique_id = "SN123456789"
    config_entry.runtime_data.coordinator = MagicMock()
    config_entry.runtime_data.client.available_sensors.return_value = [
        "temperature",
        "ph",
    ]  # Only some sensors
    config_entry.runtime_data.device_properties = mock_device_info

    async_add_entities = MagicMock()

    # Mock TYPE_CHECKING behavior
    original_type_checking = sensor_module.TYPE_CHECKING
    sensor_module.TYPE_CHECKING = False

    try:
        # Should be an async function, but we'll test the entity creation logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run the setup
        loop.run_until_complete(
            async_setup_entry(hass, config_entry, async_add_entities)
        )

        # Verify that async_add_entities was called
        async_add_entities.assert_called_once()

        # Get the entities that were created
        entities = list(async_add_entities.call_args[0][0])

        # Should only create entities for available sensors (temperature, ph)
        assert len(entities) == 2
        entity_keys = [entity.entity_description.key for entity in entities]
        assert "temperature" in entity_keys
        assert "ph" in entity_keys
        assert "orp" not in entity_keys  # Not in available sensors

    finally:
        sensor_module.TYPE_CHECKING = original_type_checking
        loop.close()


def test_sensor_tuple_data_handling(mock_device_info) -> None:
    """Test sensor handling of tuple data instead of list."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": (30.0, "°C"),  # Tuple instead of list
    }
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 30.0
    assert sensor.native_unit_of_measurement == "°C"


def test_sensor_single_value_tuple(mock_device_info) -> None:
    """Test sensor with single-value tuple."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "temperature": (30.0,),  # Single value tuple
    }
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.native_value == 30.0
    assert sensor.native_unit_of_measurement is None  # No unit available


@pytest.mark.parametrize(
    ("sensor_key", "expected_category"),
    [
        ("temperature", None),
        ("ph", None),
        ("orp", None),
        ("ph_type_dosing", EntityCategory.DIAGNOSTIC),
        ("peristaltic_ph_dosing", EntityCategory.DIAGNOSTIC),
        ("ofa_ph_value", EntityCategory.DIAGNOSTIC),
        ("orp_type_dosing", EntityCategory.DIAGNOSTIC),
        ("peristaltic_orp_dosing", EntityCategory.DIAGNOSTIC),
        ("ofa_orp_value", EntityCategory.DIAGNOSTIC),
        ("ph_calibration_type", EntityCategory.DIAGNOSTIC),
        ("ph_calibration_offset", EntityCategory.DIAGNOSTIC),
        ("ph_calibration_slope", EntityCategory.DIAGNOSTIC),
        ("orp_calibration_type", EntityCategory.DIAGNOSTIC),
        ("orp_calibration_offset", EntityCategory.DIAGNOSTIC),
        ("orp_calibration_slope", EntityCategory.DIAGNOSTIC),
    ],
)
def test_sensor_entity_categories(
    mock_coordinator, mock_device_info, sensor_key, expected_category
) -> None:
    """Test that all sensors have correct entity categories."""
    description = get_description(sensor_key)
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    assert sensor.entity_category == expected_category


@pytest.mark.parametrize(
    ("sensor_key", "expected_enabled"),
    [
        ("temperature", True),
        ("ph", True),
        ("orp", True),
        ("ph_type_dosing", True),
        ("peristaltic_ph_dosing", False),
        ("ofa_ph_value", False),
        ("orp_type_dosing", False),
        ("peristaltic_orp_dosing", False),
        ("ofa_orp_value", False),
        ("ph_calibration_type", False),
        ("ph_calibration_offset", False),
        ("ph_calibration_slope", False),
        ("orp_calibration_type", False),
        ("orp_calibration_offset", False),
        ("orp_calibration_slope", False),
    ],
)
def test_sensor_entity_registry_enabled_default(
    mock_coordinator, mock_device_info, sensor_key, expected_enabled
) -> None:
    """Test that sensors have correct enabled-by-default status."""
    description = get_description(sensor_key)
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    if expected_enabled:
        # Should be None or True (default is enabled)
        assert sensor.entity_registry_enabled_default in (None, True)
    else:
        assert sensor.entity_registry_enabled_default is False


def test_sensor_available_property(mock_coordinator, mock_device_info) -> None:
    """Test the available property from PooldoseEntity."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    # Mock the CoordinatorEntity.available property (the ultimate parent)
    with patch.object(
        CoordinatorEntity, "available", new_callable=PropertyMock
    ) as mock_super_available:
        mock_super_available.return_value = True

        # Should be available when all conditions are met
        assert sensor.available is True

        # Should be unavailable when coordinator doesn't have the key
        mock_coordinator.data = {"other_sensor": [1, "unit"]}
        assert sensor.available is False

        # Should be unavailable when coordinator data is None
        mock_coordinator.data = None
        assert sensor.available is False

        # Should be unavailable when super().available is False
        mock_coordinator.data = {"temperature": [25.5, "°C"]}
        mock_super_available.return_value = False
        assert sensor.available is False


def test_sensor_available_with_empty_coordinator_data(mock_device_info) -> None:
    """Test available property when coordinator data is empty dict."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {}  # Empty dict
    description = get_description("temperature")
    sensor = PooldoseSensor(
        coordinator,
        description,
        "SN123456789",
        mock_device_info,
    )

    # Mock the CoordinatorEntity.available property to return True
    with patch.object(
        CoordinatorEntity, "available", new_callable=PropertyMock
    ) as mock_super_available:
        mock_super_available.return_value = True

        # Should be unavailable when key not in empty data
        assert sensor.available is False


def test_pooldose_entity_available_with_empty_coordinator_data(
    mock_device_info,
) -> None:
    """Test PooldoseEntity available property when coordinator data is empty dict."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {}  # Empty dict
    description = EntityDescription(key="temperature")

    entity = PooldoseEntity(
        coordinator,
        "SN123456789",
        mock_device_info,
        description,
    )

    # Mock the CoordinatorEntity.available property to return True
    with patch.object(
        CoordinatorEntity, "available", new_callable=PropertyMock
    ) as mock_super_available:
        mock_super_available.return_value = True

        # Should be unavailable when key not in empty data
        assert entity.available is False
