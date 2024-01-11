"""Test Roborock Sensors."""
from unittest.mock import patch

from roborock import DeviceData, HomeDataDevice
from roborock.cloud_api import RoborockMqttClient
from roborock.const import (
    FILTER_REPLACE_TIME,
    MAIN_BRUSH_REPLACE_TIME,
    SENSOR_DIRTY_REPLACE_TIME,
    SIDE_BRUSH_REPLACE_TIME,
)
from roborock.roborock_message import RoborockMessage, RoborockMessageProtocol

from homeassistant.core import HomeAssistant

from .mock_data import CONSUMABLE, STATUS, USER_DATA

from tests.common import MockConfigEntry


async def test_sensors(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Test sensors and check test values are correctly set."""
    assert len(hass.states.async_all("sensor")) == 28
    assert hass.states.get("sensor.roborock_s7_maxv_main_brush_time_left").state == str(
        MAIN_BRUSH_REPLACE_TIME - 74382
    )
    assert hass.states.get("sensor.roborock_s7_maxv_side_brush_time_left").state == str(
        SIDE_BRUSH_REPLACE_TIME - 74382
    )
    assert hass.states.get("sensor.roborock_s7_maxv_filter_time_left").state == str(
        FILTER_REPLACE_TIME - 74382
    )
    assert hass.states.get("sensor.roborock_s7_maxv_sensor_time_left").state == str(
        SENSOR_DIRTY_REPLACE_TIME - 74382
    )
    assert hass.states.get("sensor.roborock_s7_maxv_cleaning_time").state == "1176"
    assert (
        hass.states.get("sensor.roborock_s7_maxv_total_cleaning_time").state == "74382"
    )
    assert hass.states.get("sensor.roborock_s7_maxv_status").state == "charging"
    assert (
        hass.states.get("sensor.roborock_s7_maxv_total_cleaning_area").state == "1159.2"
    )
    assert hass.states.get("sensor.roborock_s7_maxv_cleaning_area").state == "21.0"
    assert hass.states.get("sensor.roborock_s7_maxv_vacuum_error").state == "none"
    assert hass.states.get("sensor.roborock_s7_maxv_battery").state == "100"
    assert hass.states.get("sensor.roborock_s7_maxv_dock_error").state == "ok"
    assert (
        hass.states.get("sensor.roborock_s7_maxv_last_clean_begin").state
        == "2023-01-01T03:22:10+00:00"
    )
    assert (
        hass.states.get("sensor.roborock_s7_maxv_last_clean_end").state
        == "2023-01-01T03:43:58+00:00"
    )


async def test_listener_update(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that when we receive a mqtt topic, we successfully update the entity."""
    assert hass.states.get("sensor.roborock_s7_maxv_status").state == "charging"
    # Listeners are global based on uuid - so this is okay
    client = RoborockMqttClient(
        USER_DATA, DeviceData(device=HomeDataDevice("abc123", "", "", "", ""), model="")
    )
    # Test Status
    with patch("roborock.api.AttributeCache.value", STATUS.as_dict()):
        # Symbolizes a mqtt message coming in
        client.on_message_received(
            [
                RoborockMessage(
                    protocol=RoborockMessageProtocol.GENERAL_REQUEST,
                    payload=b'{"t": 1699464794, "dps": {"121": 5}}',
                )
            ]
        )
    # Test consumable
    assert hass.states.get("sensor.roborock_s7_maxv_filter_time_left").state == str(
        FILTER_REPLACE_TIME - 74382
    )
    with patch("roborock.api.AttributeCache.value", CONSUMABLE.as_dict()):
        client.on_message_received(
            [
                RoborockMessage(
                    protocol=RoborockMessageProtocol.GENERAL_REQUEST,
                    payload=b'{"t": 1699464794, "dps": {"127": 743}}',
                )
            ]
        )
    assert hass.states.get("sensor.roborock_s7_maxv_filter_time_left").state == str(
        FILTER_REPLACE_TIME - 743
    )
