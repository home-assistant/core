"""Tests for Hue scene select entities."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform


async def test_scene_select_initial_state(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that scene select entities are created with correct initial state."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # Test Room has "Regular Test Scene" active (static) from fixture
    state = hass.states.get("select.test_room_scene")
    assert state is not None
    assert state.state == "Regular Test Scene"
    assert "Regular Test Scene" in state.attributes["options"]

    # Test Room has a smart scene active from fixture
    state = hass.states.get("select.test_room_smart_scene")
    assert state is not None
    assert state.state == "Smart Test Scene"
    assert "Smart Test Scene" in state.attributes["options"]

    # Test Zone has "Dynamic Test Scene" active (dynamic_palette) from fixture
    state = hass.states.get("select.test_zone_scene")
    assert state is not None
    assert state.state == "Dynamic Test Scene"
    assert "Dynamic Test Scene" in state.attributes["options"]

    # Test Zone has no smart scenes — entity exists but with empty options
    state = hass.states.get("select.test_zone_smart_scene")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["options"] == []


async def test_scene_select_becomes_inactive(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that the select entity reflects unknown state when no scene is active."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # Verify starting state
    assert hass.states.get("select.test_room_scene").state == "Regular Test Scene"

    # Simulate regular scene becoming inactive
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

    # Select should now have no active option
    assert hass.states.get("select.test_room_scene").state == STATE_UNKNOWN

    # Reactivate the scene
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

    assert hass.states.get("select.test_room_scene").state == "Regular Test Scene"


async def test_scene_select_activate_option(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that selecting an option calls the bridge scene recall API."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # Select an option by calling the select_option service
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test_room_scene", "option": "Regular Test Scene"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Bridge API should have been called with the correct scene id
    regular_scene_id = "cdbf3740-7977-4a11-8275-8c78636ad4bd"
    assert len(mock_bridge_v2.mock_requests) > 0
    last_request = mock_bridge_v2.mock_requests[-1]
    assert regular_scene_id in last_request["path"]


async def test_smart_scene_select_active(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test smart scene select entity state transitions."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # Smart scene starts active
    assert hass.states.get("select.test_room_smart_scene").state == "Smart Test Scene"

    smart_scene_id = "8abe5a3e-94c8-4058-908f-56241818509a"

    # Deactivate smart scene
    mock_bridge_v2.api.emit_event(
        "update",
        {"id": smart_scene_id, "type": "smart_scene", "state": "inactive"},
    )
    await hass.async_block_till_done()

    assert hass.states.get("select.test_room_smart_scene").state == STATE_UNKNOWN

    # Reactivate smart scene
    mock_bridge_v2.api.emit_event(
        "update",
        {"id": smart_scene_id, "type": "smart_scene", "state": "active"},
    )
    await hass.async_block_till_done()

    assert hass.states.get("select.test_room_smart_scene").state == "Smart Test Scene"


async def test_smart_scene_select_activate_option(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that selecting a smart scene option calls the bridge smart_scene recall API."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test_room_smart_scene", "option": "Smart Test Scene"},
        blocking=True,
    )
    await hass.async_block_till_done()

    smart_scene_id = "8abe5a3e-94c8-4058-908f-56241818509a"
    assert len(mock_bridge_v2.mock_requests) > 0
    last_request = mock_bridge_v2.mock_requests[-1]
    assert smart_scene_id in last_request["path"]


@pytest.mark.parametrize(
    ("entity_id", "expected_options"),
    [
        ("select.test_room_scene", ["Regular Test Scene"]),
        ("select.test_room_smart_scene", ["Smart Test Scene"]),
        ("select.test_zone_scene", ["Dynamic Test Scene"]),
        ("select.test_zone_smart_scene", []),
    ],
)
async def test_scene_select_options(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    entity_id: str,
    expected_options: list[str],
) -> None:
    """Test that each select entity exposes the correct scene options for its group."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == expected_options
