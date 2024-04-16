"""Philips Hue scene platform tests for V2 bridge/api."""

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform
from .const import FAKE_SCENE


async def test_scene(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_bridge_v2,
    v2_resources_test_data,
) -> None:
    """Test if (config) scenes get created."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "scene")
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
    assert test_entity.attributes["brightness"] == 46.85
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
    assert test_entity.attributes["brightness"] == 100.0
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
    hass: HomeAssistant, mock_bridge_v2, v2_resources_test_data
) -> None:
    """Test calling the turn on service on a scene."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "scene")

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
    hass: HomeAssistant, mock_bridge_v2, v2_resources_test_data
) -> None:
    """Test calling the advanced turn on service on a scene."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "scene")

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
    hass: HomeAssistant, mock_bridge_v2, v2_resources_test_data
) -> None:
    """Test scene events from bridge."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "scene")

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
    assert test_entity.attributes["brightness"] == 65.0

    # test update
    updated_resource = {**FAKE_SCENE}
    updated_resource["actions"][0]["action"]["dimming"]["brightness"] = 35.0
    mock_bridge_v2.api.emit_event("update", updated_resource)
    await hass.async_block_till_done()
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.attributes["brightness"] == 35.0

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
