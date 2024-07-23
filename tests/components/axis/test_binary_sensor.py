"""Axis binary sensor platform tests."""

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import RtspEventMock
from .const import NAME


@pytest.mark.parametrize(
    ("event", "entity_id"),
    [
        (
            {
                "topic": "tns1:VideoSource/tnsaxis:DayNightVision",
                "source_name": "VideoSourceConfigurationToken",
                "source_idx": "1",
                "data_type": "DayNight",
                "data_value": "1",
            },
            "daynight_1",
        ),
        (
            {
                "topic": "tns1:AudioSource/tnsaxis:TriggerLevel",
                "source_name": "channel",
                "source_idx": "1",
                "data_type": "Sound",
                "data_value": "0",
            },
            "sound_1",
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
            "pir_sensor",
        ),
        (
            {
                "topic": "tns1:Device/tnsaxis:Sensor/PIR",
                "data_type": "state",
                "data_value": "0",
                "source_name": "sensor",
                "source_idx": "0",
            },
            "pir_0",
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/FenceGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            "fence_guard_profile_1",
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/MotionGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            "motion_guard_profile_1",
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/LoiteringGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            "loitering_guard_profile_1",
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            },
            "vmd4_profile_1",
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1",
                "data_type": "active",
                "data_value": "1",
            },
            "object_analytics_scenario_1",
        ),
        # Events with names generated from event ID and topic
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile9",
                "data_type": "active",
                "data_value": "1",
            },
            "vmd4_camera1profile9",
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario8",
                "data_type": "active",
                "data_value": "1",
            },
            "object_analytics_device1scenario8",
        ),
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_rtsp_event: RtspEventMock,
    event: dict[str, str],
    entity_id: str,
) -> None:
    """Test that sensors are loaded properly."""
    mock_rtsp_event(**event)
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1
    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_{entity_id}") == snapshot


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
@pytest.mark.usefixtures("config_entry_setup")
async def test_unsupported_events(
    hass: HomeAssistant,
    mock_rtsp_event: RtspEventMock,
    event: dict[str, str],
) -> None:
    """Validate nothing breaks with unsupported events."""
    mock_rtsp_event(**event)
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 0
