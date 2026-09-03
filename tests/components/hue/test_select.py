"""Tests for Hue scene select entities."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.hue.v2.select import HueSceneSelectEntity
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform

TEST_ROOM_ID = "6ddc9066-7e7d-4a03-a773-c73937968296"
TEST_ZONE_ID = "7cee478d-6455-483a-9e32-9f9fdcbcc4f6"
TEST_ROOM_SCENE_ENTITY = "select.test_room_test_room_scene"
DUPLICATE_SCENE_ID = "22222222-3333-4444-8555-666666666666"
LITERAL_SUFFIX_SCENE_ID = "33333333-4444-4555-8666-777777777777"


async def test_scene_select_initial_state(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that scene select entities are created with correct initial state."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # A smart scene and its effective regular scene can both be active. The smart
    # scene is the top-level selection shown by the Hue app.
    state = hass.states.get("select.test_room_test_room_scene")
    assert state is not None
    assert state.state == "Smart Test Scene"
    assert state.attributes["options"] == [
        "Regular Test Scene",
        "Smart Test Scene",
    ]
    assert hass.states.get("select.test_room_test_room_smart_scene") is None

    # Test Zone has "Dynamic Test Scene" active (dynamic_palette) from fixture
    state = hass.states.get("select.test_zone_scene")
    assert state is not None
    assert state.state == "Dynamic Test Scene"
    assert state.attributes["options"] == ["Dynamic Test Scene"]
    assert hass.states.get("select.test_zone_smart_scene") is None


async def test_scene_select_becomes_inactive(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that the select entity reflects unknown state when no scene is active."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # The active smart scene takes precedence over its effective regular scene.
    assert (
        hass.states.get("select.test_room_test_room_scene").state == "Smart Test Scene"
    )

    smart_scene_id = "8abe5a3e-94c8-4058-908f-56241818509a"
    regular_scene_id = "cdbf3740-7977-4a11-8275-8c78636ad4bd"

    # When the smart scene stops, fall back to the still-active regular scene.
    mock_bridge_v2.api.emit_event(
        "update",
        {"id": smart_scene_id, "type": "smart_scene", "state": "inactive"},
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("select.test_room_test_room_scene").state
        == "Regular Test Scene"
    )

    # Once both scenes are inactive, the select has no active option.
    mock_bridge_v2.api.emit_event(
        "update",
        {
            "id": regular_scene_id,
            "type": "scene",
            "status": {"active": "inactive"},
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("select.test_room_test_room_scene").state == STATE_UNKNOWN

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

    assert (
        hass.states.get("select.test_room_test_room_scene").state
        == "Regular Test Scene"
    )


async def test_scene_select_activate_option(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test that selecting an option calls the bridge scene recall API."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # Select an option by calling the select_option service
    mock_bridge_v2.mock_requests.clear()
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.test_room_test_room_scene",
            "option": "Regular Test Scene",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Bridge API should have been called with the correct scene id
    regular_scene_id = "cdbf3740-7977-4a11-8275-8c78636ad4bd"
    assert len(mock_bridge_v2.mock_requests) == 1
    path = mock_bridge_v2.mock_requests[0]["path"]
    assert "/scene/" in path
    assert regular_scene_id in path


async def test_scene_select_disambiguates_duplicate_names(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test duplicate regular scene names are exposed and recalled distinctly."""
    test_data = deepcopy(v2_resources_test_data)
    duplicate_scene = deepcopy(
        next(
            resource
            for resource in test_data
            if resource["type"] == "scene"
            and resource["metadata"]["name"] == "Regular Test Scene"
        )
    )
    duplicate_scene["id"] = DUPLICATE_SCENE_ID
    duplicate_scene["status"] = {
        "active": "inactive",
        "last_recall": "2025-09-12T11:41:46.318Z",
    }
    test_data.append(duplicate_scene)

    await mock_bridge_v2.api.load_test_data(test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    state = hass.states.get("select.test_room_test_room_scene")
    assert state is not None
    assert state.state == "Smart Test Scene"
    # The duplicate sorts before the original on scene id, so it keeps the bare name.
    assert state.attributes["options"] == [
        "Regular Test Scene",
        "Regular Test Scene (2)",
        "Smart Test Scene",
    ]

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.test_room_test_room_scene",
            "option": "Regular Test Scene",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    last_request = mock_bridge_v2.mock_requests[-1]
    assert "/scene/" in last_request["path"]
    assert DUPLICATE_SCENE_ID in last_request["path"]


@pytest.mark.parametrize(
    ("option", "expected_scene_id"),
    [
        pytest.param(
            "Regular Test Scene",
            DUPLICATE_SCENE_ID,
            id="duplicate_keeps_bare_name",
        ),
        pytest.param(
            "Regular Test Scene (2) (2)",
            LITERAL_SUFFIX_SCENE_ID,
            id="literal_name_is_disambiguated",
        ),
    ],
)
async def test_scene_select_disambiguated_label_does_not_shadow_scene_name(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    option: str,
    expected_scene_id: str,
) -> None:
    """Test a generated duplicate label cannot shadow a literal scene name."""
    test_data = deepcopy(v2_resources_test_data)
    regular_scene = next(
        resource
        for resource in test_data
        if resource["type"] == "scene"
        and resource["metadata"]["name"] == "Regular Test Scene"
    )

    duplicate_scene = deepcopy(regular_scene)
    duplicate_scene["id"] = DUPLICATE_SCENE_ID
    duplicate_scene["status"]["active"] = "inactive"
    test_data.append(duplicate_scene)

    literal_suffix_scene = deepcopy(regular_scene)
    literal_suffix_scene["id"] = LITERAL_SUFFIX_SCENE_ID
    literal_suffix_scene["metadata"]["name"] = "Regular Test Scene (2)"
    literal_suffix_scene["status"]["active"] = "inactive"
    test_data.append(literal_suffix_scene)

    await mock_bridge_v2.api.load_test_data(test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    state = hass.states.get(TEST_ROOM_SCENE_ENTITY)
    assert state is not None
    assert state.attributes["options"] == [
        "Regular Test Scene",
        "Regular Test Scene (2)",
        "Regular Test Scene (2) (2)",
        "Smart Test Scene",
    ]

    mock_bridge_v2.mock_requests.clear()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": TEST_ROOM_SCENE_ENTITY, "option": option},
        blocking=True,
    )
    assert expected_scene_id in mock_bridge_v2.mock_requests[0]["path"]


async def test_scene_select_refreshes_options_for_scene_events(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test add, rename, and delete events refresh the unified scene options."""
    test_data = deepcopy(v2_resources_test_data)
    regular_scene = next(
        resource
        for resource in test_data
        if resource["type"] == "scene"
        and resource["metadata"]["name"] == "Regular Test Scene"
    )
    smart_scene = next(
        resource for resource in test_data if resource["type"] == "smart_scene"
    )

    await mock_bridge_v2.api.load_test_data(test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    added_scene = deepcopy(regular_scene)
    added_scene["id"] = "22222222-3333-4444-8555-666666666666"
    added_scene["metadata"]["name"] = "Added scene"
    added_scene["status"]["active"] = "inactive"
    mock_bridge_v2.api.emit_event("add", added_scene)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_room_test_room_scene")
    assert state is not None
    assert state.attributes["options"] == [
        "Added scene",
        "Regular Test Scene",
        "Smart Test Scene",
    ]

    renamed_scene = deepcopy(added_scene)
    renamed_scene["metadata"]["name"] = "Renamed scene"
    mock_bridge_v2.api.emit_event("update", renamed_scene)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_room_test_room_scene")
    assert state.attributes["options"] == [
        "Regular Test Scene",
        "Renamed scene",
        "Smart Test Scene",
    ]

    # Deleting the active smart scene removes its option and exposes its effective
    # regular scene as the current selection.
    mock_bridge_v2.api.emit_event("delete", smart_scene)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_room_test_room_scene")
    assert state.state == "Regular Test Scene"
    assert state.attributes["options"] == [
        "Regular Test Scene",
        "Renamed scene",
    ]


async def test_scene_select_prefers_active_smart_scene(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test smart scene state transitions in the unified scene select."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    # Smart scene starts active
    assert (
        hass.states.get("select.test_room_test_room_scene").state == "Smart Test Scene"
    )

    smart_scene_id = "8abe5a3e-94c8-4058-908f-56241818509a"

    # Deactivate smart scene
    mock_bridge_v2.api.emit_event(
        "update",
        {"id": smart_scene_id, "type": "smart_scene", "state": "inactive"},
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("select.test_room_test_room_scene").state
        == "Regular Test Scene"
    )

    # Reactivate smart scene
    mock_bridge_v2.api.emit_event(
        "update",
        {"id": smart_scene_id, "type": "smart_scene", "state": "active"},
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("select.test_room_test_room_scene").state == "Smart Test Scene"
    )


async def test_scene_select_activate_smart_scene_option(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test selecting a smart scene uses the smart scene recall API."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    mock_bridge_v2.mock_requests.clear()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test_room_test_room_scene", "option": "Smart Test Scene"},
        blocking=True,
    )
    await hass.async_block_till_done()

    smart_scene_id = "8abe5a3e-94c8-4058-908f-56241818509a"
    assert len(mock_bridge_v2.mock_requests) == 1
    path = mock_bridge_v2.mock_requests[0]["path"]
    assert "/smart_scene/" in path
    assert smart_scene_id in path


async def test_scene_select_disambiguates_duplicate_smart_scene_names(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test duplicate smart scene names are exposed and recalled distinctly."""
    test_data = deepcopy(v2_resources_test_data)
    duplicate_smart_scene = deepcopy(
        next(resource for resource in test_data if resource["type"] == "smart_scene")
    )
    duplicate_smart_scene_id = "11111111-2222-4333-8444-555555555555"
    duplicate_smart_scene["id"] = duplicate_smart_scene_id
    duplicate_smart_scene["state"] = "inactive"
    test_data.append(duplicate_smart_scene)

    await mock_bridge_v2.api.load_test_data(test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    state = hass.states.get("select.test_room_test_room_scene")
    assert state is not None
    # The duplicate sorts before the original on scene id, so it keeps the bare name.
    assert state.state == "Smart Test Scene (2)"
    assert state.attributes["options"] == [
        "Regular Test Scene",
        "Smart Test Scene",
        "Smart Test Scene (2)",
    ]

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.test_room_test_room_scene",
            "option": "Smart Test Scene",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    last_request = mock_bridge_v2.mock_requests[-1]
    assert "/smart_scene/" in last_request["path"]
    assert duplicate_smart_scene_id in last_request["path"]


async def test_scene_select_disambiguates_names_across_scene_types(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test identical regular and smart scene names remain independently selectable."""
    test_data = deepcopy(v2_resources_test_data)
    smart_scene = next(
        resource for resource in test_data if resource["type"] == "smart_scene"
    )
    smart_scene["metadata"]["name"] = "Regular Test Scene"

    await mock_bridge_v2.api.load_test_data(test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    state = hass.states.get("select.test_room_test_room_scene")
    assert state is not None
    # The smart scene sorts before the regular scene on scene id.
    assert state.state == "Regular Test Scene"
    assert state.attributes["options"] == [
        "Regular Test Scene",
        "Regular Test Scene (2)",
    ]

    mock_bridge_v2.mock_requests.clear()
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.test_room_test_room_scene",
            "option": "Regular Test Scene (2)",
        },
        blocking=True,
    )
    assert "/scene/" in mock_bridge_v2.mock_requests[0]["path"]

    mock_bridge_v2.mock_requests.clear()
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.test_room_test_room_scene",
            "option": "Regular Test Scene",
        },
        blocking=True,
    )
    assert "/smart_scene/" in mock_bridge_v2.mock_requests[0]["path"]


@pytest.mark.parametrize(
    ("entity_id", "expected_options"),
    [
        (
            "select.test_room_test_room_scene",
            ["Regular Test Scene", "Smart Test Scene"],
        ),
        ("select.test_zone_scene", ["Dynamic Test Scene"]),
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


async def test_scene_select_removed_when_group_deleted(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test that deleting a Hue group removes its scene select entity."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    assert hass.states.get(TEST_ROOM_SCENE_ENTITY) is not None
    assert entity_registry.async_get(TEST_ROOM_SCENE_ENTITY) is not None

    mock_bridge_v2.api.emit_event(
        "delete",
        {"type": "room", "id": TEST_ROOM_ID},
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ROOM_SCENE_ENTITY) is None
    assert entity_registry.async_get(TEST_ROOM_SCENE_ENTITY) is None


@pytest.mark.parametrize(
    ("source_id", "new_id", "new_name", "entity_id"),
    [
        pytest.param(
            TEST_ROOM_ID,
            "aaaaaaaa-bbbb-4ccc-8ddd-111111111111",
            "New Room",
            "select.new_room_new_room_scene",
            id="room",
        ),
        pytest.param(
            TEST_ZONE_ID,
            "aaaaaaaa-bbbb-4ccc-8ddd-222222222222",
            "New Zone",
            "select.new_zone_scene",
            id="zone",
        ),
    ],
)
async def test_scene_select_created_when_group_added(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    source_id: str,
    new_id: str,
    new_name: str,
    entity_id: str,
) -> None:
    """Test that adding a Hue group at runtime creates its scene select entity."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    assert hass.states.get(entity_id) is None

    new_group = deepcopy(
        next(
            resource
            for resource in v2_resources_test_data
            if resource["id"] == source_id
        )
    )
    new_group["id"] = new_id
    new_group["metadata"]["name"] = new_name
    mock_bridge_v2.api.emit_event("add", new_group)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["options"] == []


async def test_scene_select_refreshes_options_missed_before_subscribe(
    hass: HomeAssistant, mock_bridge_v2: Mock, v2_resources_test_data: JsonArrayType
) -> None:
    """Test options include a scene added after init and before subscribe."""
    test_data = deepcopy(v2_resources_test_data)
    regular_scene = next(
        resource
        for resource in test_data
        if resource["type"] == "scene"
        and resource["metadata"]["name"] == "Regular Test Scene"
    )
    late_scene = deepcopy(regular_scene)
    late_scene["id"] = "44444444-5555-4666-8777-888888888888"
    late_scene["metadata"]["name"] = "Late scene"
    late_scene["status"]["active"] = "inactive"

    original_added_to_hass = HueSceneSelectEntity.async_added_to_hass

    async def async_added_to_hass_with_late_scene(
        self: HueSceneSelectEntity,
    ) -> None:
        if self.unique_id == f"{TEST_ROOM_ID}_scene_select":
            mock_bridge_v2.api.emit_event("add", late_scene)
        await original_added_to_hass(self)

    await mock_bridge_v2.api.load_test_data(test_data)
    with patch.object(
        HueSceneSelectEntity,
        "async_added_to_hass",
        async_added_to_hass_with_late_scene,
    ):
        await setup_platform(hass, mock_bridge_v2, [Platform.SCENE, Platform.SELECT])

    state = hass.states.get(TEST_ROOM_SCENE_ENTITY)
    assert state is not None
    assert state.attributes["options"] == [
        "Late scene",
        "Regular Test Scene",
        "Smart Test Scene",
    ]
