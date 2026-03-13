"""Tests for Hue scene activity sensors (active scene / smart scene tracking)."""

from __future__ import annotations

from unittest.mock import Mock

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform


async def test_scene_activity_sensors(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that hue scene events update the scene activity sensors."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    # Load scene + sensor (for activity sensors) + light (for grouped light attrs)
    await setup_platform(
        hass,
        mock_bridge_v2,
        [Platform.SCENE, Platform.SENSOR, Platform.LIGHT, Platform.BINARY_SENSOR],
    )

    # Regular scene in fixture starts already active with mode static; manager prefilled it
    assert (
        hass.states.get("sensor.test_room_scene").state
        == "scene.test_room_regular_test_scene"
    )
    assert hass.states.get("sensor.test_room_scene_name").state == "Regular Test Scene"
    # Static mode -> dynamic binary sensor off
    assert hass.states.get("binary_sensor.test_room_dynamic_scene").state == "off"
    # Prefilled last recall timestamp from fixture
    assert (
        hass.states.get("sensor.test_room_last_scene_recall").state
        == "2025-09-12T11:41:46+00:00"
    )

    # smart scene sensors prefilled as active
    assert (
        hass.states.get("sensor.test_room_smart_scene").state
        == "scene.test_room_smart_test_scene"
    )
    assert (
        hass.states.get("sensor.test_room_smart_scene_name").state == "Smart Test Scene"
    )

    # First, simulate the regular scene being turned inactive after startup
    regular_scene_id = "cdbf3740-7977-4a11-8275-8c78636ad4bd"
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {"active": "inactive"},
        },
    )
    await hass.async_block_till_done()

    # Regular scene sensors should now revert to unknown
    assert hass.states.get("sensor.test_room_scene").state == STATE_UNKNOWN
    assert hass.states.get("sensor.test_room_scene_name").state == STATE_UNKNOWN
    assert (
        hass.states.get("binary_sensor.test_room_dynamic_scene").state == STATE_UNKNOWN
    )
    assert hass.states.get("sensor.test_room_last_scene_recall").state == STATE_UNKNOWN

    # Reactivate the regular scene with a new last_recall timestamp
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {
                "active": "static",
                "last_recall": "2025-12-31T23:59:59.999Z",
            },
        },
    )
    await hass.async_block_till_done()

    # Regular scene sensors now populated
    assert (
        hass.states.get("sensor.test_room_scene").state
        == "scene.test_room_regular_test_scene"
    )
    assert hass.states.get("sensor.test_room_scene_name").state == "Regular Test Scene"
    assert (
        hass.states.get("sensor.test_room_last_scene_recall").state
        == "2025-12-31T23:59:59+00:00"
    )
    assert hass.states.get("binary_sensor.test_room_dynamic_scene").state == "off"

    # Simulate enable dynamic palette
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {
                "active": "dynamic_palette",
                "last_recall": "2026-01-01T00:00:00.000Z",
            },
        },
    )
    await hass.async_block_till_done()

    # dynamic binary sensor now on; last_recall updated; other sensors unchanged
    assert hass.states.get("sensor.test_room_scene_name").state == "Regular Test Scene"
    assert (
        hass.states.get("sensor.test_room_last_scene_recall").state
        == "2026-01-01T00:00:00+00:00"
    )
    assert hass.states.get("binary_sensor.test_room_dynamic_scene").state == "on"

    # Deactivate the regular scene
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {"active": "inactive"},
        },
    )
    await hass.async_block_till_done()

    # Sensors revert to unknown
    assert hass.states.get("sensor.test_room_scene").state == STATE_UNKNOWN
    assert hass.states.get("sensor.test_room_scene_name").state == STATE_UNKNOWN
    assert (
        hass.states.get("binary_sensor.test_room_dynamic_scene").state == STATE_UNKNOWN
    )
    assert hass.states.get("sensor.test_room_last_scene_recall").state == STATE_UNKNOWN

    # Smart scene currently active -> now deactivate
    smart_scene_id = "8abe5a3e-94c8-4058-908f-56241818509a"
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": smart_scene_id,
            "type": "smart_scene",
            "state": "inactive",
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_room_smart_scene").state == STATE_UNKNOWN
    assert hass.states.get("sensor.test_room_smart_scene_name").state == STATE_UNKNOWN

    # Reactivate smart scene
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": smart_scene_id,
            "type": "smart_scene",
            "state": "active",
        },
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.test_room_smart_scene").state
        == "scene.test_room_smart_test_scene"
    )
    assert (
        hass.states.get("sensor.test_room_smart_scene_name").state == "Smart Test Scene"
    )
