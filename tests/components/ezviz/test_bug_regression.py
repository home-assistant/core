"""Regression tests to ensure the EZVIZ sensor KeyError bug doesn't reoccur."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.ezviz.sensor import (
    SENSOR_TYPES,
    EzvizSensor,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_mode_sensor_keyerror_regression() -> None:
    """Regression test for the KeyError: 'mode' bug.

    This test would have caught the original bug where:
    1. Code tried to create a sensor with key "mode"
    2. But "mode" was not defined in SENSOR_TYPES
    3. This caused KeyError: 'mode' during sensor setup

    The bug was introduced in commit 9394546668b and fixed by adding
    the missing "mode" sensor type to SENSOR_TYPES.
    """

    # Verify that "mode" is now properly defined in SENSOR_TYPES
    assert "mode" in SENSOR_TYPES, (
        "The 'mode' sensor type should be defined in SENSOR_TYPES"
    )

    # Verify the sensor type has proper configuration
    mode_sensor = SENSOR_TYPES["mode"]
    assert mode_sensor.key == "mode"
    assert mode_sensor.translation_key == "mode"
    assert mode_sensor.entity_registry_enabled_default is False


async def test_sensor_setup_with_mode_data_no_keyerror() -> None:
    """Test that sensor setup with 'mode' data doesn't cause KeyError.

    This test simulates the exact scenario that caused the original bug.
    """

    # Mock coordinator with data that includes the problematic "mode" sensor
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "camera1": {
            "name": "Test Camera",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "device_sub_category": "CS-C6N-A0-1D2WFR",
            "version": "5.3.0",
            "status": 1,
            "battery_level": 85,
            "alarm_sound_mod": "High",
            "optionals": {
                "Record_Mode": {
                    "mode": "continuous"  # This is the problematic data structure
                }
            },
        }
    }

    # Mock config entry
    mock_entry = MockConfigEntry(
        domain="ezviz",
        data={
            "session_id": "test",
            "rf_session_id": "test",
            "type": "EZVIZ_CLOUD_ACCOUNT",
        },
    )
    mock_entry.runtime_data = mock_coordinator

    # Mock the async_add_entities callback
    mock_add_entities = MagicMock()

    # This would have failed before the fix with KeyError: 'mode'
    # Now it should work correctly
    await async_setup_entry(
        hass=MagicMock(spec=HomeAssistant),
        entry=mock_entry,
        async_add_entities=mock_add_entities,
    )

    # Verify that entities were added successfully
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]

    # Should have created entities for the sensors
    assert len(entities) > 0

    # Verify that all created sensors have valid entity descriptions
    for entity in entities:
        assert entity.entity_description is not None
        assert entity.entity_description.key in SENSOR_TYPES


async def test_all_sensor_types_have_descriptions() -> None:
    """Test that all sensor types have proper entity descriptions.

    This test ensures that any sensor type referenced in the code
    has a corresponding entry in SENSOR_TYPES.
    """

    # All sensor types should have proper descriptions
    sensors_with_device_class = {"battery_level"}

    for sensor_type, description in SENSOR_TYPES.items():
        assert description is not None, (
            f"Sensor type {sensor_type} should have a description"
        )
        assert description.key == sensor_type, f"Sensor type {sensor_type} key mismatch"

        if sensor_type in sensors_with_device_class:
            # These sensors use device_class instead of translation_key
            assert description.device_class is not None, (
                f"Sensor {sensor_type} should have device_class"
            )
        else:
            # Other sensors should have translation_key
            assert description.translation_key is not None, (
                f"Sensor type {sensor_type} should have translation_key"
            )


async def test_sensor_types_consistency() -> None:
    """Test consistency between sensor creation logic and SENSOR_TYPES.

    This test would catch cases where new sensor types are added to the
    creation logic but not to SENSOR_TYPES (like the original bug).
    """

    # Get all sensor keys that the code might try to create
    # These should all be defined in SENSOR_TYPES
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
        "mode",  # This was the missing one that caused the bug
    ]

    # Verify all potential sensor keys are defined in SENSOR_TYPES
    missing_keys = [
        sensor_key
        for sensor_key in potential_sensor_keys
        if sensor_key not in SENSOR_TYPES
    ]

    assert not missing_keys, f"Missing sensor types in SENSOR_TYPES: {missing_keys}"


async def test_ezviz_sensor_instantiation_with_all_types() -> None:
    """Test that EzvizSensor can be instantiated with all sensor types.

    This test would catch KeyError issues during sensor instantiation.
    """

    # Mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "C666666": {
            "name": "Test Camera",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "device_sub_category": "CS-C6N-A0-1D2WFR",
            "version": "5.3.0",
            "status": 1,
            "battery_level": 85,
            "alarm_sound_mod": "High",
        }
    }

    # Test that EzvizSensor can be instantiated with all sensor types

    for sensor_type in SENSOR_TYPES:
        # This would have failed for "mode" before the fix
        sensor = EzvizSensor(mock_coordinator, "C666666", sensor_type)
        assert sensor.entity_description is not None
        assert sensor.entity_description.key == sensor_type


async def test_commit_9394546668b_regression() -> None:
    """Specific regression test for the changes in commit 9394546668b.

    This commit added:
    1. New sensor creation logic for optionals (lines 108-113)
    2. New sensor creation logic for "mode" (lines 115-116)
    3. New sensor types in SENSOR_TYPES

    The bug was that "mode" was referenced in the creation logic
    but not added to SENSOR_TYPES.
    """

    # Verify that all sensor types added in that commit are present
    commit_9394546668b_sensor_types = [
        "Record_Mode",
        "battery_camera_work_mode",
        "powerStatus",
        "OnlineStatus",
        "mode",  # This was the missing one
    ]

    for sensor_type in commit_9394546668b_sensor_types:
        assert sensor_type in SENSOR_TYPES, (
            f"Commit 9394546668b sensor type {sensor_type} should be in SENSOR_TYPES"
        )

    # Verify that the "mode" sensor has the correct configuration
    mode_sensor = SENSOR_TYPES["mode"]
    assert mode_sensor.entity_registry_enabled_default is False, (
        "Mode sensor should be disabled by default like other optional sensors"
    )


async def test_no_keyerror_during_sensor_creation() -> None:
    """Test that no KeyError occurs during sensor creation with realistic data.

    This test uses the exact data structure that was causing the original bug.
    """

    # Mock coordinator with the exact data structure that caused the bug
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
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
                "Record_Mode": {
                    "mode": "continuous"  # This was causing the KeyError
                },
            },
        }
    }

    # Mock config entry
    mock_entry = MockConfigEntry(
        domain="ezviz",
        data={
            "session_id": "test",
            "rf_session_id": "test",
            "type": "EZVIZ_CLOUD_ACCOUNT",
        },
    )
    mock_entry.runtime_data = mock_coordinator

    # Mock the async_add_entities callback
    mock_add_entities = MagicMock()

    # This should not raise a KeyError anymore
    try:
        await async_setup_entry(
            hass=MagicMock(spec=HomeAssistant),
            entry=mock_entry,
            async_add_entities=mock_add_entities,
        )
    except KeyError as e:
        if "mode" in str(e):
            pytest.fail(f"KeyError for 'mode' sensor still exists: {e}")
        else:
            raise  # Re-raise if it's a different KeyError

    # Verify that entities were added successfully
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]

    # Should have created multiple entities including the mode sensor
    assert len(entities) > 0

    # Verify that the mode sensor was created
    mode_entities = [entity for entity in entities if entity._sensor_name == "mode"]
    assert len(mode_entities) > 0, "Mode sensor should have been created"
