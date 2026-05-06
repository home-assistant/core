"""Tests for the todo triggers."""

from typing import Any

import pytest

from homeassistant.components import automation
from homeassistant.components.todo import (
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntityFeature,
)
from homeassistant.components.todo.const import ATTR_ITEM, ATTR_STATUS, TodoServices
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

from . import MockTodoListEntity, create_mock_platform

from tests.common import async_mock_service, mock_device_registry

TODO_ENTITY_ID1 = "todo.list_one"
TODO_ENTITY_ID2 = "todo.list_two"


@pytest.fixture(autouse=True)
async def todo_lists(
    hass: HomeAssistant,
) -> tuple[MockTodoListEntity, MockTodoListEntity]:
    """Create two todo list entities via the mock platform."""
    entity1 = _make_entity(
        TODO_ENTITY_ID1,
        unique_id="list_one",
        items=[
            TodoItem(
                summary="existing_item",
                uid="existing_id",
                status=TodoItemStatus.NEEDS_ACTION,
            )
        ],
    )
    entity2 = _make_entity(TODO_ENTITY_ID2, unique_id="list_two")
    await create_mock_platform(hass, [entity1, entity2])
    return entity1, entity2


@pytest.fixture
def target_todo_lists(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Associate todo list entities with different targets.

    Sets up the following target structure (per entity):
    - floor_list_one / area_list_one: floor and area for list_one only
    - floor_list_two / area_list_two: floor and area for list_two only
    - label_both: label shared by both entities
    - label_list_one / label_list_two: labels for one entity only
    - device_list_one / device_list_two: devices for one entity only
    """
    floor_list_one = floor_registry.async_create("floor_list_one")
    area_list_one = area_registry.async_create(
        "area_list_one", floor_id=floor_list_one.floor_id
    )
    floor_list_two = floor_registry.async_create("floor_list_two")
    area_list_two = area_registry.async_create(
        "area_list_two", floor_id=floor_list_two.floor_id
    )

    label_both = label_registry.async_create("label_both_lists")
    label_list_one = label_registry.async_create("label_list_one")
    label_list_two = label_registry.async_create("label_list_two")

    device_list_one = dr.DeviceEntry(id="device_list_one")
    device_list_two = dr.DeviceEntry(id="device_list_two")
    mock_device_registry(
        hass,
        {
            device_list_one.id: device_list_one,
            device_list_two.id: device_list_two,
        },
    )

    entity_registry.async_update_entity(
        TODO_ENTITY_ID1,
        area_id=area_list_one.id,
        labels={label_both.label_id, label_list_one.label_id},
        device_id=device_list_one.id,
    )
    entity_registry.async_update_entity(
        TODO_ENTITY_ID2,
        area_id=area_list_two.id,
        labels={label_both.label_id, label_list_two.label_id},
        device_id=device_list_two.id,
    )


@pytest.fixture
def service_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "item_added")


def _assert_service_calls(
    service_calls: list[ServiceCall], expected_calls: list[dict[str, Any]]
) -> None:
    """Assert that the service calls match the expected calls."""
    assert len(service_calls) == len(expected_calls), (
        f"Expected {len(expected_calls)} calls, got {len(service_calls)}"
    )
    for call, expected in zip(service_calls, expected_calls, strict=True):
        for key, value in expected.items():
            assert call.data.get(key) == value, (
                f"Expected call data[{key}] to be {value}, got {call.data.get(key)}"
            )


async def _setup_automation(hass: HomeAssistant, target: dict[str, Any]) -> None:
    """Set up an automation with the todo trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": [
                    {
                        CONF_PLATFORM: "todo.item_added",
                        CONF_TARGET: target,
                    },
                    {
                        CONF_PLATFORM: "todo.item_completed",
                        CONF_TARGET: target,
                    },
                    {
                        CONF_PLATFORM: "todo.item_removed",
                        CONF_TARGET: target,
                    },
                ],
                "action": {
                    "service": "test.item_added",
                    "data": {
                        "platform": "{{ trigger.platform }}",
                        "entity_id": "{{ trigger.entity_id }}",
                        "item_ids": "{{ trigger.item_ids }}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()


def _make_entity(
    entity_id: str,
    items: list[TodoItem] | None = None,
    unique_id: str | None = None,
) -> MockTodoListEntity:
    """Create a mock todo entity with the given items."""
    entity = MockTodoListEntity(items or [])
    entity.entity_id = entity_id
    entity._attr_unique_id = unique_id
    entity._attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )
    return entity


async def _add_item(hass: HomeAssistant, entity_id: str, item: str) -> None:
    """Add an item to the entity."""
    await hass.services.async_call(
        DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ENTITY_ID: entity_id, ATTR_ITEM: item},
        blocking=True,
    )


async def _remove_item(hass: HomeAssistant, entity_id: str, item: str) -> None:
    await hass.services.async_call(
        DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ENTITY_ID: entity_id, ATTR_ITEM: [item]},
        blocking=True,
    )


async def _complete_item(hass: HomeAssistant, entity_id: str, item: str) -> None:
    await hass.services.async_call(
        DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_ITEM: item,
            ATTR_STATUS: TodoItemStatus.COMPLETED,
        },
        blocking=True,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_item_change_triggers(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test item change triggers fire."""

    await _setup_automation(hass, {CONF_ENTITY_ID: TODO_ENTITY_ID1})

    # ensure that there is 1 pre-existing item in the list,
    # so that we test that triggers only fire for new ones
    state = hass.states.get(TODO_ENTITY_ID1)
    assert state is not None
    assert state.state == "1"

    item1 = "item_id"
    await _add_item(hass, TODO_ENTITY_ID1, item1)
    await _add_item(hass, TODO_ENTITY_ID1, "other_item")

    _assert_service_calls(
        service_calls,
        [
            {"platform": "todo.item_added", "entity_id": TODO_ENTITY_ID1},
            {"platform": "todo.item_added", "entity_id": TODO_ENTITY_ID1},
        ],
    )
    assert len(service_calls[0].data["item_ids"]) == 1
    assert len(service_calls[1].data["item_ids"]) == 1
    item1_id = service_calls[0].data["item_ids"][0]
    item2_id = service_calls[1].data["item_ids"][0]
    assert item1_id != item2_id
    service_calls.clear()

    await _complete_item(hass, TODO_ENTITY_ID1, item1)
    _assert_service_calls(
        service_calls,
        [
            {
                "platform": "todo.item_completed",
                "entity_id": TODO_ENTITY_ID1,
                "item_ids": [item1_id],
            },
        ],
    )
    service_calls.clear()

    await _remove_item(hass, TODO_ENTITY_ID1, item1)
    _assert_service_calls(
        service_calls,
        [
            {
                "platform": "todo.item_removed",
                "entity_id": TODO_ENTITY_ID1,
                "item_ids": [item1_id],
            },
        ],
    )


@pytest.mark.parametrize(
    ("action_method", "item_summary", "expected_trigger_platform"),
    [
        (_add_item, "new_item", "todo.item_added"),
        (_complete_item, "loaded_item", "todo.item_completed"),
        (_remove_item, "loaded_item", "todo.item_removed"),
    ],
)
@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_item_change_triggers_ignore_initial_unknown(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    todo_lists: tuple[MockTodoListEntity, MockTodoListEntity],
    action_method: Any,
    item_summary: str,
    expected_trigger_platform: str,
) -> None:
    """Test triggers do not fire when items load for the first time."""
    entity, _ = todo_lists
    entity._attr_todo_items = None
    entity.async_write_ha_state()
    await hass.async_block_till_done()
    assert (state := hass.states.get(TODO_ENTITY_ID1))
    assert state.state == STATE_UNKNOWN

    await _setup_automation(hass, {CONF_ENTITY_ID: TODO_ENTITY_ID1})

    entity._attr_todo_items = [
        TodoItem(
            summary="loaded_item", uid="loaded_id", status=TodoItemStatus.NEEDS_ACTION
        )
    ]
    entity.async_write_ha_state()
    await hass.async_block_till_done()
    _assert_service_calls(service_calls, [])
    assert (state := hass.states.get(TODO_ENTITY_ID1))
    assert state.state == "1"

    await action_method(hass, TODO_ENTITY_ID1, item_summary)
    _assert_service_calls(
        service_calls,
        [{"platform": expected_trigger_platform, "entity_id": TODO_ENTITY_ID1}],
    )


@pytest.mark.usefixtures("enable_labs_preview_features", "target_todo_lists")
@pytest.mark.parametrize(
    "included_target",
    [
        {CONF_ENTITY_ID: TODO_ENTITY_ID1},
        {ATTR_AREA_ID: "area_list_one"},
        {ATTR_FLOOR_ID: "floor_list_one"},
        {ATTR_LABEL_ID: "label_list_one"},
        {ATTR_DEVICE_ID: "device_list_one"},
    ],
)
async def test_item_change_trigger_does_not_fire_for_other_entity(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    included_target: dict[str, Any],
) -> None:
    """Test item_added trigger only fires for the targeted entity."""
    included_entity = TODO_ENTITY_ID1
    excluded_entity = TODO_ENTITY_ID2

    await _setup_automation(hass, included_target)

    # Add item to excluded entity (not targeted)
    await _add_item(hass, excluded_entity, "Untargeted item")
    _assert_service_calls(service_calls, [])

    # Add item to included entity (targeted)
    await _add_item(hass, included_entity, "Targeted item")
    _assert_service_calls(
        service_calls,
        [{"platform": "todo.item_added", "entity_id": included_entity}],
    )
    targeted_item_id = service_calls[0].data["item_ids"][0]
    service_calls.clear()

    # Complete item on excluded entity (not targeted) - should not fire
    await _complete_item(hass, excluded_entity, "Untargeted item")
    _assert_service_calls(service_calls, [])

    # Complete item on included entity (targeted) - should fire
    await _complete_item(hass, included_entity, targeted_item_id)
    _assert_service_calls(
        service_calls,
        [
            {
                "platform": "todo.item_completed",
                "entity_id": included_entity,
                "item_ids": [targeted_item_id],
            }
        ],
    )
    service_calls.clear()

    # Remove item on excluded entity (not targeted) - should not fire
    await _remove_item(hass, excluded_entity, "Untargeted item")
    _assert_service_calls(service_calls, [])

    # Remove item on included entity (targeted) - should fire
    await _remove_item(hass, included_entity, targeted_item_id)
    _assert_service_calls(
        service_calls,
        [
            {
                "platform": "todo.item_removed",
                "entity_id": included_entity,
                "item_ids": [targeted_item_id],
            }
        ],
    )


@pytest.mark.usefixtures("enable_labs_preview_features", "target_todo_lists")
async def test_new_entity_added_to_target_fires_triggers(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test triggers fire for a new entity added to an existing target."""
    todo_entity_id3 = "todo.list_three"

    # Set up automation targeting label_list_one (initially only entity1)
    await _setup_automation(hass, {ATTR_LABEL_ID: "label_list_one"})

    entity3 = _make_entity(
        todo_entity_id3,
        unique_id="list_three",
        items=[
            TodoItem(
                summary="prefilled_item",
                uid="prefilled_id",
                status=TodoItemStatus.NEEDS_ACTION,
            )
        ],
    )
    await create_mock_platform(hass, [entity3])

    # Changing items on the new entity should NOT fire (not in label yet)
    await _add_item(hass, todo_entity_id3, "item_before_label")
    await _complete_item(hass, todo_entity_id3, "item_before_label")
    await _remove_item(hass, todo_entity_id3, "item_before_label")
    _assert_service_calls(service_calls, [])

    # Now add the label to the third entity so the trigger starts tracking it
    entity_registry.async_update_entity(
        todo_entity_id3,
        labels={"label_list_one"},
    )
    await hass.async_block_till_done()

    # Adding an item to the third entity should now fire the trigger
    await _add_item(hass, todo_entity_id3, "item_after_label")
    await _complete_item(hass, todo_entity_id3, "item_after_label")
    await _remove_item(hass, todo_entity_id3, "item_after_label")
    _assert_service_calls(
        service_calls,
        [
            {"platform": "todo.item_added", "entity_id": todo_entity_id3},
            {"platform": "todo.item_completed", "entity_id": todo_entity_id3},
            {"platform": "todo.item_removed", "entity_id": todo_entity_id3},
        ],
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_trigger_skips_missing_entity(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a missing entity does not prevent other entities from being tracked."""
    nonexistent_entity_id = "todo.nonexistent"

    # Target both a valid entity and a non-existent one
    await _setup_automation(
        hass, {CONF_ENTITY_ID: [TODO_ENTITY_ID1, nonexistent_entity_id]}
    )

    assert f"Skipping entity {nonexistent_entity_id}" in caplog.text

    # The valid entity should still be tracked
    await _add_item(hass, TODO_ENTITY_ID1, "item_one")
    _assert_service_calls(
        service_calls,
        [{"platform": "todo.item_added", "entity_id": TODO_ENTITY_ID1}],
    )


@pytest.mark.usefixtures("enable_labs_preview_features", "target_todo_lists")
async def test_entity_rejoining_label_does_not_fire_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test removing and re-adding an entity to a target does not fire stale triggers."""
    label_both = label_registry.async_get_label_by_name("label_both_lists")
    assert label_both is not None
    label_both_id = label_both.label_id

    await _setup_automation(hass, {ATTR_LABEL_ID: label_both_id})

    # Verify triggers fire normally for list_one
    await _add_item(hass, TODO_ENTITY_ID1, "tracked_item")
    _assert_service_calls(
        service_calls,
        [{"platform": "todo.item_added", "entity_id": TODO_ENTITY_ID1}],
    )
    service_calls.clear()

    entity_registry.async_update_entity(TODO_ENTITY_ID1, labels=set())
    await hass.async_block_till_done()

    # Adding items should not fire for the now untracked entity
    await _add_item(hass, TODO_ENTITY_ID1, "untracked_item")
    _assert_service_calls(service_calls, [])

    # Re-adding the label should not fire
    entity_registry.async_update_entity(TODO_ENTITY_ID1, labels={label_both_id})
    await hass.async_block_till_done()
    _assert_service_calls(service_calls, [])

    # Adding new items should fire again
    await _add_item(hass, TODO_ENTITY_ID1, "new_item_after_rejoin")
    _assert_service_calls(
        service_calls,
        [{"platform": "todo.item_added", "entity_id": TODO_ENTITY_ID1}],
    )


@pytest.mark.usefixtures("enable_labs_preview_features", "target_todo_lists")
@pytest.mark.parametrize(
    "trigger_target",
    [
        {CONF_ENTITY_ID: [TODO_ENTITY_ID1, TODO_ENTITY_ID2]},
        {ATTR_AREA_ID: ["area_list_one", "area_list_two"]},
        {ATTR_FLOOR_ID: ["floor_list_one", "floor_list_two"]},
        {ATTR_LABEL_ID: "label_both_lists"},
        {ATTR_DEVICE_ID: ["device_list_one", "device_list_two"]},
    ],
    ids=["entity_id", "area", "floor", "label", "device"],
)
async def test_item_change_trigger_with_multiple_target_entities(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_target: dict[str, Any],
) -> None:
    """Test item_added trigger fires for multiple targeted entities."""
    await _setup_automation(hass, target=trigger_target)

    await _add_item(hass, TODO_ENTITY_ID1, "Item on list one")
    await _add_item(hass, TODO_ENTITY_ID2, "Item on list two")
    _assert_service_calls(
        service_calls,
        [
            {"platform": "todo.item_added", "entity_id": TODO_ENTITY_ID1},
            {"platform": "todo.item_added", "entity_id": TODO_ENTITY_ID2},
        ],
    )
    item_one_id = service_calls[0].data["item_ids"][0]
    item_two_id = service_calls[1].data["item_ids"][0]
    service_calls.clear()

    await _complete_item(hass, TODO_ENTITY_ID1, item_one_id)
    await _complete_item(hass, TODO_ENTITY_ID2, item_two_id)
    _assert_service_calls(
        service_calls,
        [
            {
                "platform": "todo.item_completed",
                "entity_id": TODO_ENTITY_ID1,
                "item_ids": [item_one_id],
            },
            {
                "platform": "todo.item_completed",
                "entity_id": TODO_ENTITY_ID2,
                "item_ids": [item_two_id],
            },
        ],
    )
    service_calls.clear()

    await _remove_item(hass, TODO_ENTITY_ID1, item_one_id)
    await _remove_item(hass, TODO_ENTITY_ID2, item_two_id)
    _assert_service_calls(
        service_calls,
        [
            {
                "platform": "todo.item_removed",
                "entity_id": TODO_ENTITY_ID1,
                "item_ids": [item_one_id],
            },
            {
                "platform": "todo.item_removed",
                "entity_id": TODO_ENTITY_ID2,
                "item_ids": [item_two_id],
            },
        ],
    )
