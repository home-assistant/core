"""Philips Hue scene platform tests for V2 bridge/api."""

from unittest.mock import Mock

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .const import FAKE_SCENE


async def test_scene(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test if (config) scenes get created."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 3 entities should be created from test data
    assert len(hass.states.async_all()) == 3

    # test (dynamic) scene for a hue zone
    test_entity = hass.states.get("scene.test_zone_dynamic_test_scene")
    assert test_entity is not None
    assert test_entity.name == "Test Zone Dynamic Test Scene"
    assert test_entity.state == STATE_UNKNOWN
    assert test_entity.attributes["group_name"] == "Test Zone"
    assert test_entity.attributes["group_type"] == "zone"
    assert test_entity.attributes["name"] == "Dynamic Test Scene"
    assert test_entity.attributes["speed"] == 0.6269841194152832
    assert test_entity.attributes["brightness"] == 119
    assert test_entity.attributes["is_dynamic"] is True

    # test (regular) scene for a hue room
    test_entity = hass.states.get("scene.test_room_regular_test_scene")
    assert test_entity is not None
    assert test_entity.name == "Test Room Regular Test Scene"
    assert test_entity.state == STATE_UNKNOWN
    assert test_entity.attributes["group_name"] == "Test Room"
    assert test_entity.attributes["group_type"] == "room"
    assert test_entity.attributes["name"] == "Regular Test Scene"
    assert test_entity.attributes["speed"] == 0.5
    assert test_entity.attributes["brightness"] == 255
    assert test_entity.attributes["is_dynamic"] is False

    # test smart scene
    test_entity = hass.states.get("scene.test_room_smart_test_scene")
    assert test_entity is not None
    assert test_entity.name == "Test Room Smart Test Scene"
    assert test_entity.state == STATE_UNKNOWN
    assert test_entity.attributes["group_name"] == "Test Room"
    assert test_entity.attributes["group_type"] == "room"
    assert test_entity.attributes["name"] == "Smart Test Scene"
    assert test_entity.attributes["active_timeslot_id"] == 1
    assert test_entity.attributes["active_timeslot_name"] == "wednesday"
    assert test_entity.attributes["active_scene"] == "Regular Test Scene"
    assert test_entity.attributes["is_active"] is True

    # scene entities should have be assigned to the room/zone device/service
    for entity_id in (
        "scene.test_zone_dynamic_test_scene",
        "scene.test_room_regular_test_scene",
        "scene.test_room_smart_test_scene",
    ):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry
        assert entity_entry.device_id is not None


async def test_scene_turn_on_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test calling the turn on service on a scene."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)

    test_entity_id = "scene.test_room_regular_test_scene"

    # call the HA turn_on service
    await hass.services.async_call(
        "scene",
        "turn_on",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    # PUT request should have been sent to device with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"]["recall"] == {"action": "active"}

    # test again with sending transition
    await hass.services.async_call(
        "scene",
        "turn_on",
        {"entity_id": test_entity_id, "transition": 0.25},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 2
    assert mock_bridge_v2.mock_requests[1]["json"]["recall"] == {
        "action": "active",
        "duration": 200,
    }


async def test_scene_advanced_turn_on_service(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test calling the advanced turn on service on a scene."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)

    test_entity_id = "scene.test_room_regular_test_scene"

    # call the hue.activate_scene service
    await hass.services.async_call(
        "hue",
        "activate_scene",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    # PUT request should have been sent to device with correct params
    assert len(mock_bridge_v2.mock_requests) == 1
    assert mock_bridge_v2.mock_requests[0]["method"] == "put"
    assert mock_bridge_v2.mock_requests[0]["json"]["recall"] == {"action": "active"}

    # test again with sending speed and dynamic
    await hass.services.async_call(
        "hue",
        "activate_scene",
        {"entity_id": test_entity_id, "speed": 80, "dynamic": True},
        blocking=True,
    )
    assert len(mock_bridge_v2.mock_requests) == 3
    assert mock_bridge_v2.mock_requests[1]["json"]["speed"] == 0.8
    assert mock_bridge_v2.mock_requests[2]["json"]["recall"] == {
        "action": "dynamic_palette",
    }


async def test_scene_updates(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test scene events from bridge."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)

    test_entity_id = "scene.test_room_mocked_scene"

    # verify entity does not exist before we start
    assert hass.states.get(test_entity_id) is None

    # Add new fake scene
    mock_bridge_v2.api.emit_event("add", FAKE_SCENE)
    await hass.async_block_till_done()

    # the entity should now be available
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == STATE_UNKNOWN
    assert test_entity.name == "Test Room Mocked Scene"
    assert test_entity.attributes["brightness"] == 166

    # test update
    updated_resource = {**FAKE_SCENE}
    updated_resource["actions"][0]["action"]["dimming"]["brightness"] = 35.0
    mock_bridge_v2.api.emit_event("update", updated_resource)
    await hass.async_block_till_done()
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.attributes["brightness"] == 89

    # # test entity name changes on group name change
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "room",
            "id": "6ddc9066-7e7d-4a03-a773-c73937968296",
            "metadata": {"name": "Test Room 2"},
        },
    )
    await hass.async_block_till_done()
    test_entity = hass.states.get(test_entity_id)
    assert test_entity.attributes["group_name"] == "Test Room 2"

    # # test delete
    mock_bridge_v2.api.emit_event("delete", updated_resource)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is None


async def test_scene_activation_on_recall(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test scene activation is detected when last_recall timestamp changes.

    When a scene is recalled (activated) from any source (Hue app, physical button,
    voice assistant, or HA), the bridge updates the status.last_recall timestamp.
    This should trigger _async_record_activation() and update the scene state.
    """
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)

    test_entity_id = "scene.test_room_regular_test_scene"
    test_scene_id = "cdbf3740-7977-4a11-8275-8c78636ad4bd"

    # Verify initial state is unknown (no activation recorded yet)
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == STATE_UNKNOWN

    # Simulate scene recall by updating last_recall timestamp
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "scene",
            "id": test_scene_id,
            "status": {"last_recall": "2024-01-15T10:30:00.000Z"},
        },
    )
    await hass.async_block_till_done()

    # Scene state should now be updated (activation recorded)
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state != STATE_UNKNOWN  # State should be a timestamp now


async def test_scene_no_false_activation_on_update(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that scene updates without last_recall change don't trigger activation.

    This is the critical bug fix: when a light in an active scene is modified,
    the scene receives an update event but last_recall stays unchanged.
    We must NOT record this as a new activation.
    """
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)

    test_entity_id = "scene.test_room_regular_test_scene"
    test_scene_id = "cdbf3740-7977-4a11-8275-8c78636ad4bd"

    # First, trigger an activation with initial last_recall
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "scene",
            "id": test_scene_id,
            "status": {"last_recall": "2024-01-15T10:30:00.000Z"},
        },
    )
    await hass.async_block_till_done()

    # Get the state after first activation
    test_entity = hass.states.get(test_entity_id)
    first_activation_state = test_entity.state
    assert first_activation_state != STATE_UNKNOWN

    # Now simulate a scene update WITHOUT changing last_recall
    # (e.g., light brightness changed while scene is active)
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "scene",
            "id": test_scene_id,
            "actions": [
                {
                    "action": {
                        "dimming": {"brightness": 75.0},
                        "on": {"on": True},
                    },
                    "target": {
                        "rid": "3a6710fa-4474-4eba-b533-5e6e72968feb",
                        "rtype": "light",
                    },
                },
            ],
            # Note: last_recall is NOT included - simulates light change, not scene recall
        },
    )
    await hass.async_block_till_done()

    # State should NOT have changed (no new activation recorded)
    test_entity = hass.states.get(test_entity_id)
    assert test_entity.state == first_activation_state


async def test_smart_scene_activation_on_state_change(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test smart scene activation is detected on state transition to active.

    Smart scenes use state transition detection instead of last_recall timestamp.
    Activation should only be recorded when state changes FROM inactive TO active.
    """
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)

    test_entity_id = "scene.test_room_smart_test_scene"
    test_scene_id = "redacted-8abe5a3e-94c8-4058-908f-56241818509a"

    # Verify initial state - smart scene is already active in test data
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None

    # Set smart scene to inactive first
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "smart_scene",
            "id": test_scene_id,
            "state": "inactive",
        },
    )
    await hass.async_block_till_done()

    # Get state after deactivation
    test_entity = hass.states.get(test_entity_id)
    inactive_state = test_entity.state

    # Now activate the smart scene (state transition: inactive -> active)
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "smart_scene",
            "id": test_scene_id,
            "state": "active",
        },
    )
    await hass.async_block_till_done()

    # State should be updated (activation recorded)
    test_entity = hass.states.get(test_entity_id)
    assert test_entity.state != inactive_state  # State changed


async def test_smart_scene_no_false_activation_while_active(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test smart scene doesn't record false activation when staying active.

    When a light in an active smart scene is modified, the scene receives
    an update event but state stays 'active'. We must NOT record this as
    a new activation - only state transitions should trigger activation.
    """
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, Platform.SCENE)

    test_entity_id = "scene.test_room_smart_test_scene"
    test_scene_id = "redacted-8abe5a3e-94c8-4058-908f-56241818509a"

    # First deactivate, then activate to get a known activation timestamp
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "smart_scene",
            "id": test_scene_id,
            "state": "inactive",
        },
    )
    await hass.async_block_till_done()

    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "smart_scene",
            "id": test_scene_id,
            "state": "active",
        },
    )
    await hass.async_block_till_done()

    # Get the state after activation
    test_entity = hass.states.get(test_entity_id)
    first_activation_state = test_entity.state
    assert first_activation_state != STATE_UNKNOWN

    # Now send another update with state still 'active'
    # (simulates light modification while smart scene is active)
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "type": "smart_scene",
            "id": test_scene_id,
            "state": "active",  # State unchanged
            "active_timeslot": {
                "timeslot_id": 2,  # Different timeslot
                "weekday": "thursday",
            },
        },
    )
    await hass.async_block_till_done()

    # State should NOT have changed (no new activation recorded)
    test_entity = hass.states.get(test_entity_id)
    assert test_entity.state == first_activation_state
