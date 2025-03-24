"""Axis binary sensor platform tests."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, RtspEventMock

from tests.common import snapshot_platform


@pytest.mark.parametrize(
    "event",
    [
        (
            {
                "topic": "tns1:VideoSource/tnsaxis:DayNightVision",
                "source_name": "VideoSourceConfigurationToken",
                "source_idx": "1",
                "data_type": "DayNight",
                "data_value": "1",
            }
        ),
        (
            {
                "topic": "tns1:AudioSource/tnsaxis:TriggerLevel",
                "source_name": "channel",
                "source_idx": "1",
                "data_type": "Sound",
                "data_value": "0",
            }
        ),
        (
            {
                "topic": "tns1:Device/tnsaxis:IO/Port",
                "data_type": "state",
                "data_value": "0",
                "operation": "Initialized",
                "source_name": "port",
                "source_idx": "0",
            }
        ),
        (
            {
                "topic": "tns1:Device/tnsaxis:Sensor/PIR",
                "data_type": "state",
                "data_value": "0",
                "source_name": "sensor",
                "source_idx": "0",
            }
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/FenceGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            }
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/MotionGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            }
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/LoiteringGuard/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            }
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile1",
                "data_type": "active",
                "data_value": "1",
            }
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1",
                "data_type": "active",
                "data_value": "1",
            }
        ),
        # Events with names generated from event ID and topic
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile9",
                "data_type": "active",
                "data_value": "1",
            }
        ),
        (
            {
                "topic": "tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario8",
                "data_type": "active",
                "data_value": "1",
            }
        ),
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry_factory: ConfigEntryFactoryType,
    mock_rtsp_event: RtspEventMock,
    event: dict[str, str],
) -> None:
    """Test that sensors are loaded properly."""
    with patch("homeassistant.components.axis.PLATFORMS", [Platform.BINARY_SENSOR]):
        config_entry = await config_entry_factory()
    mock_rtsp_event(**event)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "event",
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
