"""Tests for sensor.py with Uhoo sensors."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.uhoo.sensor import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SENSOR_TYPES,
    UhooSensorEntity,
    UnitOfTemperature,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


@pytest.fixture
def mock_coordinator():
    """Mock the UhooDataUpdateCoordinator."""
    coordinator = MagicMock()
    coordinator.data = {}
    return coordinator


@pytest.fixture
def mock_device():
    """Mock a uHoo device."""
    device = MagicMock()
    device.humidity = 45.5
    device.temperature = 22.0
    device.co = 1.5
    device.co2 = 450.0
    device.pm25 = 12.3
    device.air_pressure = 1013.25
    device.tvoc = 150.0
    device.no2 = 20.0
    device.ozone = 30.0
    device.virus_index = 2.0
    device.mold_index = 1.5
    device.device_name = "Test Device"
    device.serial_number = "23f9239m92m3ffkkdkdd"
    device.user_settings = {"temp": "c"}  # Add user_settings dictionary
    return device


@pytest.fixture
def mock_config_entry():
    """Mock a config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.runtime_data = None
    return config_entry


@pytest.fixture
def mock_add_entities():
    """Mock the add_entities callback."""
    return MagicMock(spec=AddConfigEntryEntitiesCallback)


def test_sensor_entity_descriptions() -> None:
    """Test that all sensor descriptions are properly defined."""
    assert len(SENSOR_TYPES) == 11  # We have 11 sensor types

    # Check a few key sensors
    humidity_desc = next(d for d in SENSOR_TYPES if d.key == "humidity")
    assert humidity_desc.device_class == SensorDeviceClass.HUMIDITY
    assert humidity_desc.native_unit_of_measurement == PERCENTAGE
    assert humidity_desc.state_class == SensorStateClass.MEASUREMENT
    assert callable(humidity_desc.value_fn)

    temp_desc = next(d for d in SENSOR_TYPES if d.key == "temperature")
    assert temp_desc.device_class == SensorDeviceClass.TEMPERATURE
    assert temp_desc.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert temp_desc.state_class == SensorStateClass.MEASUREMENT
    assert callable(temp_desc.value_fn)

    # Check virus and mold sensors don't have device_class
    virus_desc = next(d for d in SENSOR_TYPES if d.key == "virus_index")
    mold_desc = next(d for d in SENSOR_TYPES if d.key == "mold_index")
    assert virus_desc.device_class is None
    assert mold_desc.device_class is None


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_coordinator,
    mock_add_entities,
    mock_device,
) -> None:
    """Test setting up sensor entities."""
    # Setup coordinator with one device
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_coordinator.data = {serial_number: mock_device}
    mock_config_entry.runtime_data = mock_coordinator

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Verify that entities were added
    assert mock_add_entities.called
    call_args = mock_add_entities.call_args[0][0]
    entities = list(call_args)  # Convert generator to list

    # Should create entities for each sensor type for the device
    assert len(entities) == len(SENSOR_TYPES)

    # Check that entities have the correct unique IDs
    humidity_entity = next(
        e for e in entities if e._attr_unique_id == f"{serial_number}_humidity"
    )
    assert humidity_entity is not None
    assert humidity_entity.entity_description.key == "humidity"


async def test_async_setup_entry_multiple_devices(
    hass: HomeAssistant,
    mock_config_entry,
    mock_coordinator,
    mock_add_entities,
    mock_device,
) -> None:
    """Test setting up sensor entities for multiple devices."""
    # Setup coordinator with two devices
    device1 = mock_device
    device2 = MagicMock()
    device2.device_name = "Device 2"
    device2.serial_number = "device2_serial"
    device2.humidity = 50.0
    device2.temperature = 21.0
    device2.co = 1.0
    device2.co2 = 400.0
    device2.pm25 = 10.0
    device2.air_pressure = 1010.0
    device2.tvoc = 100.0
    device2.no2 = 15.0
    device2.ozone = 25.0
    device2.virus_index = 1.0
    device2.mold_index = 1.0
    device2.user_settings = {"temp": "c"}

    mock_coordinator.data = {
        "23f9239m92m3ffkkdkdd": device1,
        "device2_serial": device2,
    }
    mock_config_entry.runtime_data = mock_coordinator

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Verify that entities were added
    assert mock_add_entities.called
    entities = list(mock_add_entities.call_args[0][0])

    # Should create entities for each sensor type for each device
    assert len(entities) == len(SENSOR_TYPES) * 2

    # Check entities for both devices exist
    device1_humidity = any(
        e._attr_unique_id == "23f9239m92m3ffkkdkdd_humidity" for e in entities
    )
    device2_humidity = any(
        e._attr_unique_id == "device2_serial_humidity" for e in entities
    )
    assert device1_humidity
    assert device2_humidity


def test_uhoo_sensor_entity_init(
    mock_coordinator,
    mock_device,
) -> None:
    """Test UhooSensorEntity initialization."""
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_coordinator.data = {serial_number: mock_device}

    # Get humidity description
    humidity_desc = next(d for d in SENSOR_TYPES if d.key == "humidity")

    # Create entity
    entity = UhooSensorEntity(humidity_desc, serial_number, mock_coordinator)

    # Check basic properties
    assert entity.entity_description == humidity_desc
    assert entity._serial_number == serial_number
    assert entity._attr_unique_id == f"{serial_number}_humidity"

    # Check device info
    assert entity._attr_device_info["identifiers"] == {(DOMAIN, serial_number)}
    assert entity._attr_device_info["name"] == "Test Device"
    assert entity._attr_device_info["manufacturer"] == MANUFACTURER
    assert entity._attr_device_info["model"] == MODEL
    assert entity._attr_device_info["serial_number"] == serial_number


def test_uhoo_sensor_entity_device_property(
    mock_coordinator,
    mock_device,
) -> None:
    """Test the device property returns correct device."""
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_coordinator.data = {serial_number: mock_device}

    humidity_desc = next(d for d in SENSOR_TYPES if d.key == "humidity")
    entity = UhooSensorEntity(humidity_desc, serial_number, mock_coordinator)

    # Device property should return the correct device
    assert entity.device == mock_device
    assert entity.device.humidity == 45.5


def test_uhoo_sensor_entity_available_property(
    mock_coordinator,
    mock_device,
) -> None:
    """Test the available property."""
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_coordinator.data = {serial_number: mock_device}

    humidity_desc = next(d for d in SENSOR_TYPES if d.key == "humidity")
    entity = UhooSensorEntity(humidity_desc, serial_number, mock_coordinator)

    # Mock parent's available property
    with patch(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.available",
        new_callable=lambda: True,
    ):
        # Entity should be available when device is in coordinator data
        assert entity.available is True

        # Remove device from coordinator data
        mock_coordinator.data = {}
        assert entity.available is False


def test_uhoo_sensor_entity_native_value(
    mock_coordinator,
    mock_device,
) -> None:
    """Test the native_value property."""
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_coordinator.data = {serial_number: mock_device}

    # Test humidity sensor
    humidity_desc = next(d for d in SENSOR_TYPES if d.key == "humidity")
    entity = UhooSensorEntity(humidity_desc, serial_number, mock_coordinator)

    assert entity.native_value == 45.5

    # Test temperature sensor
    temp_desc = next(d for d in SENSOR_TYPES if d.key == "temperature")
    entity = UhooSensorEntity(temp_desc, serial_number, mock_coordinator)

    assert entity.native_value == 22.0


def test_uhoo_sensor_entity_native_unit_of_measurement_celsius(
    mock_coordinator,
    mock_device,
) -> None:
    """Test native_unit_of_measurement for temperature in Celsius."""
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_device.user_settings = {"temp": "c"}
    mock_coordinator.data = {serial_number: mock_device}

    temp_desc = next(d for d in SENSOR_TYPES if d.key == "temperature")
    entity = UhooSensorEntity(temp_desc, serial_number, mock_coordinator)

    assert entity.native_unit_of_measurement == UnitOfTemperature.CELSIUS


def test_uhoo_sensor_entity_native_unit_of_measurement_fahrenheit(
    mock_coordinator,
    mock_device,
) -> None:
    """Test native_unit_of_measurement for temperature in Fahrenheit."""
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_device.user_settings = {"temp": "f"}
    mock_coordinator.data = {serial_number: mock_device}

    temp_desc = next(d for d in SENSOR_TYPES if d.key == "temperature")
    entity = UhooSensorEntity(temp_desc, serial_number, mock_coordinator)

    assert entity.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT


def test_uhoo_sensor_entity_native_unit_of_measurement_other_sensors(
    mock_coordinator,
    mock_device,
) -> None:
    """Test native_unit_of_measurement for non-temperature sensors."""
    serial_number = "23f9239m92m3ffkkdkdd"
    mock_coordinator.data = {serial_number: mock_device}

    # Test humidity sensor (should use default from description)
    humidity_desc = next(d for d in SENSOR_TYPES if d.key == "humidity")
    entity = UhooSensorEntity(humidity_desc, serial_number, mock_coordinator)

    # For non-temperature sensors, it should return the description's unit
    assert entity.native_unit_of_measurement == PERCENTAGE


async def test_async_setup_entry_no_devices(
    hass: HomeAssistant,
    mock_config_entry,
    mock_coordinator,
    mock_add_entities,
) -> None:
    """Test setting up sensor entities when there are no devices."""
    mock_coordinator.data = {}  # No devices
    mock_config_entry.runtime_data = mock_coordinator

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should still call add_entities but with empty generator
    assert mock_add_entities.called

    # Convert generator to list to check it's empty
    entities = list(mock_add_entities.call_args[0][0])
    assert len(entities) == 0


def test_all_sensor_types_have_value_functions() -> None:
    """Test that all sensor types have valid value functions."""
    for sensor_desc in SENSOR_TYPES:
        assert hasattr(sensor_desc, "value_fn")
        assert callable(sensor_desc.value_fn)

        # Create a mock device to test the lambda
        mock_device = MagicMock()
        # Set all possible attributes to non-None values
        fields = [
            "humidity",
            "temperature",
            "co",
            "co2",
            "pm25",
            "air_pressure",
            "tvoc",
            "no2",
            "ozone",
            "virus_index",
            "mold_index",
        ]
        for attr in fields:
            setattr(mock_device, attr, 1.0)

        # The value function should return a float or None
        result = sensor_desc.value_fn(mock_device)
        assert result is None or isinstance(result, (int, float))


@pytest.mark.parametrize(
    ("sensor_key", "expected_device_class"),
    [
        ("humidity", SensorDeviceClass.HUMIDITY),
        ("temperature", SensorDeviceClass.TEMPERATURE),
        ("co", SensorDeviceClass.CO),
        ("co2", SensorDeviceClass.CO2),
        ("pm25", SensorDeviceClass.PM25),
        ("air_pressure", SensorDeviceClass.PRESSURE),
        ("tvoc", SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS),
        ("no2", SensorDeviceClass.NITROGEN_DIOXIDE),
        ("ozone", SensorDeviceClass.OZONE),
        ("virus_index", None),  # No device class for virus_index
        ("mold_index", None),  # No device class for mold_index
    ],
)
def test_sensor_device_classes(sensor_key, expected_device_class) -> None:
    """Test that each sensor has the correct device class."""
    sensor_desc = next(d for d in SENSOR_TYPES if d.key == sensor_key)
    assert sensor_desc.device_class == expected_device_class


def test_sensor_state_classes() -> None:
    """Test that all sensors have MEASUREMENT state class."""
    for sensor_desc in SENSOR_TYPES:
        assert sensor_desc.state_class == SensorStateClass.MEASUREMENT


def test_temperature_sensor_unit_conversion_logic() -> None:
    """Test the logic for temperature unit conversion."""
    serial_number = "23f9239m92m3ffkkdkdd"

    # Create a mock device with Celsius setting
    mock_device_c = MagicMock()
    mock_device_c.device_name = "Test Device"
    mock_device_c.user_settings = {"temp": "c"}

    # Create a mock device with Fahrenheit setting
    mock_device_f = MagicMock()
    mock_device_f.device_name = "Test Device"
    mock_device_f.user_settings = {"temp": "f"}

    # Mock coordinator with Celsius setting
    coordinator_c = MagicMock()
    coordinator_c.data = {serial_number: mock_device_c}

    # Mock coordinator with Fahrenheit setting
    coordinator_f = MagicMock()
    coordinator_f.data = {serial_number: mock_device_f}

    temp_desc = next(d for d in SENSOR_TYPES if d.key == "temperature")

    # Create entities with different coordinators
    entity_c = UhooSensorEntity(temp_desc, serial_number, coordinator_c)
    entity_f = UhooSensorEntity(temp_desc, serial_number, coordinator_f)

    # Test the actual property calls
    assert entity_c.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert entity_f.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
