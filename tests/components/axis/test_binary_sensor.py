"""Axis binary sensor platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .const import NAME


@pytest.mark.parametrize(
    ("event", "entity"),
    [
        (
            {
                "topic": "tns1:VideoSource/tnsaxis:DayNightVision",
                "source_name": "VideoSourceConfigurationToken",
                "source_idx": "1",
                "data_type": "DayNight",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_daynight_1",
                "state": STATE_ON,
                "name": f"{NAME} DayNight 1",
                "device_class": BinarySensorDeviceClass.LIGHT,
            },
        ),
        (
            {
                "topic": "tns1:AudioSource/tnsaxis:TriggerLevel",
                "source_name": "channel",
                "source_idx": "1",
                "data_type": "Sound",
                "data_value": "0",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_sound_1",
                "state": STATE_OFF,
                "name": f"{NAME} Sound 1",
                "device_class": BinarySensorDeviceClass.SOUND,
            },
        ),
        (
            {
                "topic": "tns1:Device/tnsaxis:IO/Port",
                "data_type": "state",
                "data_value": "0",
                "operation": "Initialized",
                "source_name": "port",
                "source_idx": "0",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_pir_sensor",
                "state": STATE_OFF,
                "name": f"{NAME} PIR sensor",
                "device_class": BinarySensorDeviceClass.CONNECTIVITY,
            },
        ),
        (
            {
                "topic": "tns1:Device/tnsaxis:Sensor/PIR",
                "data_type": "state",
                "data_value": "0",
                "source_name": "sensor",
                "source_idx": "0",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_pir_0",
                "state": STATE_OFF,
                "name": f"{NAME} PIR 0",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/FenceGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_fence_guard_profile_1",
                "state": STATE_ON,
                "name": f"{NAME} Fence Guard Profile 1",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/MotionGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_motion_guard_profile_1",
                "state": STATE_ON,
                "name": f"{NAME} Motion Guard Profile 1",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/LoiteringGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_loitering_guard_profile_1",
                "state": STATE_ON,
                "name": f"{NAME} Loitering Guard Profile 1",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_vmd4_profile_1",
                "state": STATE_ON,
                "name": f"{NAME} VMD4 Profile 1",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1",
                "data_type": "active",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_object_analytics_scenario_1",
                "state": STATE_ON,
                "name": f"{NAME} Object Analytics Scenario 1",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
        # Events with names generated from event ID and topic
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile9",
                "data_type": "active",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_vmd4_camera1profile9",
                "state": STATE_ON,
                "name": f"{NAME} VMD4 Camera1Profile9",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario8",
                "data_type": "active",
                "data_value": "1",
            },
            {
                "id": f"{BINARY_SENSOR_DOMAIN}.{NAME}_object_analytics_device1scenario8",
                "state": STATE_ON,
                "name": f"{NAME} Object Analytics Device1Scenario8",
                "device_class": BinarySensorDeviceClass.MOTION,
            },
        ),
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    setup_config_entry: ConfigEntry,
    mock_rtsp_event: Callable[[str, str, str, str, str, str], None],
    event: dict[str, str],
    entity: dict[str, str],
) -> None:
    """Test that sensors are loaded properly."""
    mock_rtsp_event(**event)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1

    state = hass.states.get(entity["id"])
    assert state.state == entity["state"]
    assert state.name == entity["name"]
    assert state.attributes["device_class"] == entity["device_class"]


@pytest.mark.parametrize(
    ("event"),
    [
        # Event with unsupported topic
        {
            "topic": "tns1:PTZController/tnsaxis:PTZPresets/Channel_1",
            "data_type": "on_preset",
            "data_value": "1",
            "source_name": "PresetToken",
            "source_idx": "0",
        },
        # Event with unsupported source_idx
        {
            "topic": "tns1:Device/tnsaxis:IO/Port",
            "data_type": "state",
            "data_value": "0",
            "operation": "Initialized",
            "source_name": "port",
            "source_idx": "-1",
        },
        # Event with unsupported ID in topic 'ANY'
        {
            "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1ProfileANY",
            "data_type": "active",
            "data_value": "1",
        },
        {
            "topic": "tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1ScenarioANY",
            "data_type": "active",
            "data_value": "1",
        },
    ],
)
async def test_unsupported_events(
    hass: HomeAssistant,
    setup_config_entry: ConfigEntry,
    mock_rtsp_event: Callable[[str, str, str, str, str, str], None],
    event: dict[str, str],
) -> None:
    """Validate nothing breaks with unsupported events."""
    mock_rtsp_event(**event)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 0
