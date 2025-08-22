"""Test the Pooldose sensor platform."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.sensor import (
    SENSOR_DESCRIPTIONS,
    PooldoseSensor,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .conftest import SERIAL_NUMBER

from tests.common import MockConfigEntry


def get_description(key: str) -> SensorEntityDescription:
    """Return the sensor entity description for the given key."""
    return next(desc for desc in SENSOR_DESCRIPTIONS if desc.key == key)


def test_sensor_basic_properties(mock_coordinator, mock_device_info) -> None:
    """Test that the sensor has correct basic properties."""
    description = get_description("ph")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.unique_id == f"{SERIAL_NUMBER}_ph"
    assert sensor.has_entity_name is True
    assert sensor.device_class == SensorDeviceClass.PH

    assert sensor.device_info["identifiers"] == {("pooldose", SERIAL_NUMBER)}
    assert sensor.device_info["serial_number"] == SERIAL_NUMBER


def test_sensor_native_value(mock_coordinator, mock_device_info) -> None:
    """Test that the sensor returns the correct value."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_value == 25.5
    assert sensor.unique_id == f"{SERIAL_NUMBER}_temperature"


def test_sensor_temperature_unit_dynamic(mock_coordinator, mock_device_info) -> None:
    """Test that temperature sensor gets unit dynamically from API data."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_unit_of_measurement == "°C"
    assert sensor.unique_id == f"{SERIAL_NUMBER}_temperature"


def test_sensor_temperature_unit_fahrenheit(mock_coordinator, mock_device_info) -> None:
    """Test that temperature sensor handles Fahrenheit unit."""
    mock_coordinator.data = {"temperature": [77.0, "°F"]}

    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_value == 77.0
    assert sensor.native_unit_of_measurement == "°F"
    assert sensor.unique_id == f"{SERIAL_NUMBER}_temperature"


def test_sensor_static_unit_orp(mock_coordinator, mock_device_info) -> None:
    """Test that ORP sensor uses static unit definition."""
    description = get_description("orp")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_value == 650
    assert sensor.native_unit_of_measurement == "mV"
    assert sensor.unique_id == f"{SERIAL_NUMBER}_orp"


def test_sensor_ph_no_unit(mock_coordinator, mock_device_info) -> None:
    """Test that pH sensor has no unit (dimensionless)."""
    description = get_description("ph")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_value == 7.2
    assert sensor.native_unit_of_measurement is None
    assert sensor.unique_id == f"{SERIAL_NUMBER}_ph"


def test_sensor_native_value_missing_key(mock_coordinator, mock_device_info) -> None:
    """Test that the sensor returns None if the key is missing in the data."""
    mock_coordinator.data = {"temperature": [25.5, "°C"]}

    description = SensorEntityDescription(key="missing_sensor")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_value is None
    assert sensor.unique_id == f"{SERIAL_NUMBER}_missing_sensor"


def test_diagnostic_sensor_entity_category(mock_coordinator, mock_device_info) -> None:
    """Test that diagnostic sensors have correct entity category."""
    description = get_description("ph_type_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.native_value == "Automatic"
    assert sensor.unique_id == f"{SERIAL_NUMBER}_ph_type_dosing"


def test_sensor_disabled_by_default(mock_coordinator, mock_device_info) -> None:
    """Test that some sensors are disabled by default."""
    description = get_description("peristaltic_ph_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.entity_registry_enabled_default is False
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.unique_id == f"{SERIAL_NUMBER}_peristaltic_ph_dosing"


def test_sensor_empty_coordinator_data(
    mock_coordinator_empty, mock_device_info
) -> None:
    """Test sensor behavior when coordinator data is empty."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator_empty,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_value is None
    assert sensor.unique_id == f"{SERIAL_NUMBER}_temperature"


def test_sensor_unique_id_generation_with_different_serial_numbers() -> None:
    """Test that different serial numbers generate different unique IDs."""
    mock_coordinator = MagicMock(spec=PooldoseCoordinator)
    mock_coordinator.data = {"ph": [7.2, "pH"]}
    mock_coordinator.last_update_success = True

    different_serial = "SN987654321"
    mock_device_info = {
        "identifiers": {("pooldose", different_serial)},
        "name": "PoolDose Device",
        "manufacturer": "PoolDose",
        "model": "PDPR1H1HAW100",
        "serial_number": different_serial,
        "sw_version": "FW539187",
    }

    description = get_description("ph")
    sensor = PooldoseSensor(
        mock_coordinator,
        different_serial,
        mock_device_info,
        description,
    )

    assert sensor.unique_id == f"{different_serial}_ph"
    assert sensor.device_info["serial_number"] == different_serial
    assert sensor.device_info["identifiers"] == {("pooldose", different_serial)}


@pytest.mark.parametrize(
    ("sensor_key", "expected_category"),
    [
        ("temperature", None),
        ("ph", None),
        ("orp", None),
        ("ph_type_dosing", EntityCategory.DIAGNOSTIC),
        ("peristaltic_ph_dosing", EntityCategory.DIAGNOSTIC),
        ("orp_type_dosing", EntityCategory.DIAGNOSTIC),
        ("peristaltic_orp_dosing", EntityCategory.DIAGNOSTIC),
        ("ph_calibration_type", EntityCategory.DIAGNOSTIC),
        ("ph_calibration_offset", EntityCategory.DIAGNOSTIC),
        ("ph_calibration_slope", EntityCategory.DIAGNOSTIC),
        ("orp_calibration_type", EntityCategory.DIAGNOSTIC),
        ("orp_calibration_offset", EntityCategory.DIAGNOSTIC),
        ("orp_calibration_slope", EntityCategory.DIAGNOSTIC),
        ("ofa_ph_value", EntityCategory.DIAGNOSTIC),
    ],
)
def test_sensor_entity_categories(
    mock_coordinator, mock_device_info, sensor_key, expected_category
) -> None:
    """Test that all sensors have correct entity categories."""
    mock_coordinator.data = {sensor_key: ["test_value", "test_unit"]}

    description = get_description(sensor_key)
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.entity_category == expected_category
    assert sensor.unique_id == f"{SERIAL_NUMBER}_{sensor_key}"
    assert sensor.device_info["serial_number"] == SERIAL_NUMBER


@pytest.mark.parametrize(
    ("test_serial", "sensor_key"),
    [
        (SERIAL_NUMBER, "temperature"),
        ("SN987654321", "ph"),
        ("PDPR1H1HAW100_FW539187", "orp"),
        ("device_001", "ph_type_dosing"),
    ],
)
def test_sensor_unique_id_with_various_serial_numbers(
    mock_coordinator, sensor_key, test_serial
) -> None:
    """Test unique ID generation with various serial numbers."""
    mock_coordinator.data = {sensor_key: ["test_value", "test_unit"]}

    mock_device_info = {
        "identifiers": {("pooldose", test_serial)},
        "name": "PoolDose Device",
        "manufacturer": "PoolDose",
        "model": "PDPR1H1HAW100",
        "serial_number": test_serial,
        "sw_version": "FW539187",
    }

    description = get_description(sensor_key)
    sensor = PooldoseSensor(
        mock_coordinator,
        test_serial,
        mock_device_info,
        description,
    )

    expected_unique_id = f"{test_serial}_{sensor_key}"
    assert sensor.unique_id == expected_unique_id
    assert sensor.device_info["serial_number"] == test_serial
    assert sensor.device_info["identifiers"] == {("pooldose", test_serial)}


def test_sensor_available_property(mock_coordinator, mock_device_info) -> None:
    """Test the available property from PooldoseEntity."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    with patch.object(
        CoordinatorEntity, "available", new_callable=PropertyMock
    ) as mock_super_available:
        mock_super_available.return_value = True

        assert sensor.available is True
        assert sensor.unique_id == f"{SERIAL_NUMBER}_temperature"

        mock_coordinator.data = {"other_sensor": [1, "unit"]}
        assert sensor.available is False

        mock_coordinator.data = None
        assert sensor.available is False

        mock_coordinator.data = {"temperature": [25.5, "°C"]}
        mock_super_available.return_value = False
        assert sensor.available is False


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client,
    mock_device_info,
) -> None:
    """Test sensor platform setup."""
    coordinator = MagicMock(spec=PooldoseCoordinator)

    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.coordinator = coordinator
    mock_config_entry.runtime_data.client = mock_pooldose_client
    mock_config_entry.runtime_data.device_properties = mock_device_info

    mock_pooldose_client.available_sensors.return_value = ["temperature", "ph", "orp"]

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = list(async_add_entities.call_args[0][0])

    assert len(entities) == 3
    entity_keys = [entity.entity_description.key for entity in entities]
    assert "temperature" in entity_keys
    assert "ph" in entity_keys
    assert "orp" in entity_keys

    for entity in entities:
        expected_unique_id = f"{SERIAL_NUMBER}_{entity.entity_description.key}"
        assert entity.unique_id == expected_unique_id
        assert entity.device_info["serial_number"] == SERIAL_NUMBER


def test_sensor_device_info_structure(mock_coordinator, mock_device_info) -> None:
    """Test that device info structure is correctly passed through."""
    description = get_description("temperature")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    device_info = sensor.device_info

    # Test the essential device identification fields
    assert device_info["identifiers"] == {("pooldose", SERIAL_NUMBER)}
    assert device_info["serial_number"] == SERIAL_NUMBER

    # Test that the device_info contains expected manufacturer and model
    # These values should match what's actually returned by the implementation
    expected_fields = {
        "manufacturer": "SEKO",
        "hw_version": "FW123",
    }

    for field, expected_value in expected_fields.items():
        assert device_info.get(field) == expected_value, (
            f"Expected {field}={expected_value}, got {device_info.get(field)}"
        )

    # Verify additional fields that should be present
    assert "configuration_url" in device_info
    assert "connections" in device_info
    assert ("mac", "AA:BB:CC:DD:EE:FF") in device_info["connections"]


def test_all_sensor_descriptions_have_required_fields() -> None:
    """Test that all sensor descriptions have required fields."""
    for description in SENSOR_DESCRIPTIONS:
        assert description.key is not None
        if description.entity_registry_enabled_default is False:
            assert description.entity_category == EntityCategory.DIAGNOSTIC


def test_sensor_device_classes() -> None:
    """Test that sensors have correct device classes."""
    temperature_desc = get_description("temperature")
    assert temperature_desc.device_class == SensorDeviceClass.TEMPERATURE

    ph_desc = get_description("ph")
    assert ph_desc.device_class == SensorDeviceClass.PH

    orp_desc = get_description("orp")
    assert orp_desc.device_class == SensorDeviceClass.VOLTAGE


def test_sensor_string_value_handling(mock_coordinator, mock_device_info) -> None:
    """Test sensor handling of string values."""
    mock_coordinator.data = {"ph_type_dosing": ["Manual", ""]}

    description = get_description("ph_type_dosing")
    sensor = PooldoseSensor(
        mock_coordinator,
        SERIAL_NUMBER,
        mock_device_info,
        description,
    )

    assert sensor.native_value == "Manual"
    assert sensor.native_unit_of_measurement is None
    assert sensor.unique_id == f"{SERIAL_NUMBER}_ph_type_dosing"
