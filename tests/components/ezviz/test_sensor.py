"""Test the EZVIZ sensor platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.ezviz.const import DOMAIN
from homeassistant.components.ezviz.sensor import (
    SENSOR_TYPES,
    EzvizSensor,
    async_setup_entry,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator():
    """Mock the EZVIZ coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "C666666": {
            "name": "Test Camera",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "device_sub_category": "CS-C6N-A0-1D2WFR",
            "version": "5.3.0",
            "status": 1,
            "battery_level": 85,
            "alarm_sound_mod": "High",
            "last_alarm_time": "2023-01-01T12:00:00Z",
            "Seconds_Last_Trigger": 300,
            "last_alarm_pic": "http://example.com/pic.jpg",
            "supported_channels": 2,
            "local_ip": "192.168.1.100",
            "wan_ip": "203.0.113.1",
            "PIR_Status": "Active",
            "last_alarm_type_code": "PIR",
            "last_alarm_type_name": "Motion Detection",
            "Record_Mode": "continuous",
            "battery_camera_work_mode": "normal",
            "optionals": {
                "powerStatus": "on",
                "OnlineStatus": "online",
                "Record_Mode": {"mode": "continuous"},
            },
        }
    }
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        title="test-username",
        data={
            "session_id": "test-username",
            "rf_session_id": "test-password",
            "url": "apiieu.ezvizlife.com",
            "type": "EZVIZ_CLOUD_ACCOUNT",
        },
    )


async def test_sensor_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """Test sensor setup entry."""

    mock_config_entry.runtime_data = mock_coordinator

    # Mock the async_add_entities callback
    mock_add_entities = MagicMock()

    # Call the sensor setup function directly
    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Check that entities were created
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) > 0

    # Should have battery_level sensor
    battery_sensors = [
        entity for entity in entities if entity._sensor_name == "battery_level"
    ]
    assert len(battery_sensors) > 0


async def test_sensor_setup_with_mode_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """Test sensor setup with 'mode' data that was causing the KeyError."""

    mock_config_entry.runtime_data = mock_coordinator

    # Mock the async_add_entities callback
    mock_add_entities = MagicMock()

    # Call the sensor setup function directly
    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Check that entities were created
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) > 0

    # Should have mode sensor
    mode_sensors = [entity for entity in entities if entity._sensor_name == "mode"]
    assert len(mode_sensors) > 0


async def test_sensor_types_completeness() -> None:
    """Test that all sensor types referenced in the code are defined in SENSOR_TYPES."""
    # This test would have caught the bug by ensuring all sensor keys
    # that the code tries to create are actually defined in SENSOR_TYPES

    # Get all sensor keys that the code might try to create
    potential_sensor_keys = [
        "battery_level",
        "alarm_sound_mod",
        "last_alarm_time",
        "Seconds_Last_Trigger",
        "last_alarm_pic",
        "supported_channels",
        "local_ip",
        "wan_ip",
        "PIR_Status",
        "last_alarm_type_code",
        "last_alarm_type_name",
        "Record_Mode",
        "battery_camera_work_mode",
        "powerStatus",
        "OnlineStatus",
        "mode",  # This was missing before the fix!
    ]

    # Verify all potential sensor keys are defined in SENSOR_TYPES
    for sensor_key in potential_sensor_keys:
        assert sensor_key in SENSOR_TYPES, f"Missing sensor type: {sensor_key}"


async def test_ezviz_sensor_entity_creation(
    mock_coordinator: MagicMock,
) -> None:
    """Test that EzvizSensor can be created for all sensor types."""
    # Test that EzvizSensor can be instantiated with all sensor types
    for sensor_type in SENSOR_TYPES:
        sensor = EzvizSensor(mock_coordinator, "C666666", sensor_type)
        assert sensor.entity_description is not None
        assert sensor.entity_description.key == sensor_type
        assert sensor._sensor_name == sensor_type
        assert sensor._attr_unique_id == f"C666666_Test Camera.{sensor_type}"


async def test_ezviz_sensor_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test EzvizSensor native_value property."""
    # Test with a sensor that has data
    sensor = EzvizSensor(mock_coordinator, "C666666", "battery_level")
    assert sensor.native_value == 85

    # Test with a sensor that has string data
    sensor = EzvizSensor(mock_coordinator, "C666666", "alarm_sound_mod")
    assert sensor.native_value == "High"


async def test_ezviz_sensor_availability(
    mock_coordinator: MagicMock,
) -> None:
    """Test EzvizSensor availability."""
    # Test with available camera (status != 2)
    sensor = EzvizSensor(mock_coordinator, "C666666", "battery_level")
    assert sensor.available is True

    # Test with unavailable camera (status == 2)
    mock_coordinator.data["C666666"]["status"] = 2
    sensor = EzvizSensor(mock_coordinator, "C666666", "battery_level")
    assert sensor.available is False


async def test_sensor_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """Test sensor entity registry."""
    mock_config_entry.runtime_data = mock_coordinator
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ezviz.sensor.EzvizDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.ezviz.EzvizClient",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.ezviz.coordinator.EzvizDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that sensors are properly registered
    sensor_entities = [
        entity for entity in hass.states.async_all() if entity.domain == SENSOR_DOMAIN
    ]

    for entity in sensor_entities:
        registry_entry = entity_registry.async_get(entity.entity_id)
        assert registry_entry is not None
        assert registry_entry.platform == DOMAIN


async def test_sensor_device_info(
    mock_coordinator: MagicMock,
) -> None:
    """Test sensor device info."""
    sensor = EzvizSensor(mock_coordinator, "C666666", "battery_level")

    device_info = sensor.device_info
    assert device_info["identifiers"] == {(DOMAIN, "C666666")}
    assert device_info["connections"] == {("mac", "aa:bb:cc:dd:ee:ff")}
    assert device_info["manufacturer"] == "EZVIZ"
    assert device_info["model"] == "CS-C6N-A0-1D2WFR"
    assert device_info["name"] == "Test Camera"
    assert device_info["sw_version"] == "5.3.0"


async def test_sensor_setup_with_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor setup with empty coordinator data."""
    empty_coordinator = MagicMock()
    empty_coordinator.data = {}

    mock_config_entry.runtime_data = empty_coordinator
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ezviz.sensor.EzvizDataUpdateCoordinator",
        return_value=empty_coordinator,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Should not create any sensors with empty data
    sensor_entities = [
        entity for entity in hass.states.async_all() if entity.domain == SENSOR_DOMAIN
    ]
    assert len(sensor_entities) == 0


async def test_sensor_setup_with_none_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor setup with None values in sensor data."""
    coordinator_with_none = MagicMock()
    coordinator_with_none.data = {
        "C666666": {
            "name": "Test Camera",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "device_sub_category": "CS-C6N-A0-1D2WFR",
            "version": "5.3.0",
            "status": 1,
            "battery_level": None,  # None value should be filtered out
            "alarm_sound_mod": "High",
        }
    }

    mock_config_entry.runtime_data = coordinator_with_none

    # Mock the async_add_entities callback
    mock_add_entities = MagicMock()

    # Call the sensor setup function directly
    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Check that entities were created
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) > 0

    # Should have alarm_sound_mod but not battery_level (due to None value)
    sensor_names = [entity._sensor_name for entity in entities]
    assert "alarm_sound_mod" in sensor_names
    assert "battery_level" not in sensor_names


async def test_optional_sensors_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
) -> None:
    """Test that optional sensors (powerStatus, OnlineStatus) are created correctly."""

    mock_config_entry.runtime_data = mock_coordinator

    # Mock the async_add_entities callback
    mock_add_entities = MagicMock()

    # Call the sensor setup function directly
    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Check that entities were created
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) > 0

    # Check that optional sensors were created
    sensor_names = [entity._sensor_name for entity in entities]
    assert "powerStatus" in sensor_names
    assert "OnlineStatus" in sensor_names


async def test_sensor_translation_keys() -> None:
    """Test that all sensors have proper translation keys."""
    # Sensors with device_class don't need translation_key
    sensors_with_device_class = {"battery_level"}

    # Sensors that have different translation_key than sensor_type (this is valid)
    expected_translation_keys = {
        "Seconds_Last_Trigger": "seconds_last_trigger",
        "PIR_Status": "pir_status",
        "Record_Mode": "record_mode",
        "powerStatus": "power_status",
        "OnlineStatus": "online_status",
    }

    for sensor_type, description in SENSOR_TYPES.items():
        if sensor_type in sensors_with_device_class:
            # These sensors use device_class instead of translation_key
            assert description.device_class is not None, (
                f"Sensor {sensor_type} should have device_class"
            )
        else:
            # Other sensors should have translation_key
            assert description.translation_key is not None, (
                f"Missing translation_key for {sensor_type}"
            )
            # Check if this sensor has a specific expected translation_key
            expected_key = expected_translation_keys.get(sensor_type, sensor_type)
            assert description.translation_key == expected_key, (
                f"Translation key mismatch for {sensor_type}: expected {expected_key}, got {description.translation_key}"
            )


async def test_sensor_entity_registry_enabled_default() -> None:
    """Test that sensors have appropriate entity_registry_enabled_default settings."""
    # Most sensors should be enabled by default, except for some optional ones
    disabled_by_default = {
        "alarm_sound_mod",
        "last_alarm_time",
        "Seconds_Last_Trigger",
        "last_alarm_pic",
        "Record_Mode",
        "battery_camera_work_mode",
        "powerStatus",
        "OnlineStatus",
        "mode",
    }

    for sensor_type, description in SENSOR_TYPES.items():
        if sensor_type in disabled_by_default:
            assert description.entity_registry_enabled_default is False, (
                f"{sensor_type} should be disabled by default"
            )
        else:
            assert description.entity_registry_enabled_default is True, (
                f"{sensor_type} should be enabled by default"
            )
