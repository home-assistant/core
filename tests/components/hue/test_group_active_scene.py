"""Tests for active Hue scene attributes on grouped lights."""

from __future__ import annotations

from unittest.mock import Mock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform


async def test_group_active_scene_attributes(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test active_hue_scene and active_hue_smart_scene attributes update on events."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    # Load both scene and light platforms so scene recall events are processed
    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)
    await setup_platform(hass, mock_bridge_v2, Platform.LIGHT)

    grouped = hass.states.get("light.test_room")
    assert grouped is not None
    # Initially no active scenes recorded
    assert grouped.attributes.get("active_hue_scene") is None
    assert grouped.attributes.get("active_hue_scene_mode") is None
    assert grouped.attributes.get("active_hue_scene_last_recall") is None
    assert grouped.attributes.get("active_hue_smart_scene") is None

    # Activate smart scene via update event
    smart_scene_id = "redacted-8abe5a3e-94c8-4058-908f-56241818509a"
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": smart_scene_id,
            "type": "smart_scene",
            "state": "active",
        },
    )
    await hass.async_block_till_done()
    grouped = hass.states.get("light.test_room")
    assert grouped is not None
    assert grouped.attributes.get("active_hue_smart_scene") == "Smart Test Scene"

    # Simulate regular scene recall event with status
    regular_scene_id = "cdbf3740-7977-4a11-8275-8c78636ad4bd"
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {
                "active": "static",
                "last_recall": "2025-09-08T12:00:00Z",
            },
        },
    )
    await hass.async_block_till_done()

    grouped = hass.states.get("light.test_room")
    assert grouped is not None
    assert grouped.attributes["active_hue_scene"] == "Regular Test Scene"
    assert grouped.attributes["active_hue_scene_mode"] == "static"
    assert grouped.attributes["active_hue_scene_last_recall"] == "2025-09-08T12:00:00Z"

    # Simulate dynamic scene recall
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {
                "active": "dynamic_palette",
                "last_recall": "2025-09-08T12:05:00Z",
            },
        },
    )
    await hass.async_block_till_done()

    grouped = hass.states.get("light.test_room")
    assert grouped is not None
    assert grouped.attributes["active_hue_scene_mode"] == "dynamic_palette"
    assert grouped.attributes["active_hue_scene_last_recall"] == "2025-09-08T12:05:00Z"

    # Deactivate regular scene
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {"active": "inactive"},
        },
    )
    await hass.async_block_till_done()

    grouped = hass.states.get("light.test_room")
    assert grouped is not None
    assert grouped.attributes["active_hue_scene"] is None
    assert grouped.attributes["active_hue_scene_mode"] is None
    assert grouped.attributes["active_hue_scene_last_recall"] is None

    # Deactivate smart scene
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": smart_scene_id,
            "type": "smart_scene",
            "state": "inactive",
        },
    )
    await hass.async_block_till_done()
    grouped = hass.states.get("light.test_room")
    assert grouped is not None
    assert grouped.attributes.get("active_hue_smart_scene") is None
