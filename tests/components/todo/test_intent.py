"""Tests for the todo intents."""

import asyncio
import datetime as dt
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import async_mock_service
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.todo import (
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
    TodoServiceArgument,
    TodoServices,
    intent as todo_intent,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from . import MockTodoListEntity, create_mock_platform


@pytest.fixture(autouse=True)
async def setup_intents(hass: HomeAssistant) -> None:
    """Set up the intents."""
    assert await async_setup_component(hass, "homeassistant", {})
    await todo_intent.async_setup_intents(hass)


async def test_add_item_intent(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test adding items to lists using an intent."""
    assert await async_setup_component(hass, "homeassistant", {})
    await todo_intent.async_setup_intents(hass)

    entity1 = MockTodoListEntity()
    entity1._attr_name = "List 1"
    entity1.entity_id = "todo.list_1"

    entity2 = MockTodoListEntity()
    entity2._attr_name = "List 2"
    entity2.entity_id = "todo.list_2"

    await create_mock_platform(hass, [entity1, entity2])

    # Add to first list
    response = await intent.async_handle(
        hass,
        "test",
        todo_intent.INTENT_LIST_ADD_ITEM,
        {"item": {"value": " beer "}, "name": {"value": "list 1"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert response.success_results[0].name == "list 1"
    assert response.success_results[0].type == intent.IntentResponseTargetType.ENTITY
    assert response.success_results[0].id == entity1.entity_id

    assert len(entity1.items) == 1
    assert len(entity2.items) == 0
    assert entity1.items[0].summary == "Beer"  # summary is trimmed and capitalized
    assert entity1.items[0].status == TodoItemStatus.NEEDS_ACTION
    entity1.items.clear()

    # Add to second list
    response = await intent.async_handle(
        hass,
        "test",
        todo_intent.INTENT_LIST_ADD_ITEM,
        {"item": {"value": "cheese"}, "name": {"value": "List 2"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 0
    assert len(entity2.items) == 1
    assert entity2.items[0].summary == "Cheese"
    assert entity2.items[0].status == TodoItemStatus.NEEDS_ACTION

    # List name is case insensitive
    response = await intent.async_handle(
        hass,
        "test",
        todo_intent.INTENT_LIST_ADD_ITEM,
        {"item": {"value": "wine"}, "name": {"value": "lIST 2"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 0
    assert len(entity2.items) == 2
    assert entity2.items[1].summary == "Wine"
    assert entity2.items[1].status == TodoItemStatus.NEEDS_ACTION

    # Should fail if lists are not exposed
    async_expose_entity(hass, conversation.DOMAIN, entity1.entity_id, False)
    async_expose_entity(hass, conversation.DOMAIN, entity2.entity_id, False)
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_ADD_ITEM,
            {"item": {"value": "cookies"}, "name": {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason is intent.MatchFailedReason.ASSISTANT

    # Missing list
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_ADD_ITEM,
            {"item": {"value": "wine"}, "name": {"value": "This list does not exist"}},
            assistant=conversation.DOMAIN,
        )

    # Fail with empty name/item
    with pytest.raises(intent.InvalidSlotInfo):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_ADD_ITEM,
            {"item": {"value": "wine"}, "name": {"value": ""}},
            assistant=conversation.DOMAIN,
        )

    with pytest.raises(intent.InvalidSlotInfo):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_ADD_ITEM,
            {"item": {"value": ""}, "name": {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        )


async def test_add_item_intent_errors(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test errors with the add item intent."""
    test_entity._attr_name = "List 1"
    await create_mock_platform(hass, [test_entity])

    # Try to add item in list that does not exist
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_ADD_ITEM,
            {
                "item": {"value": "wine"},
                "name": {"value": "This list does not exist"},
            },
            assistant=conversation.DOMAIN,
        )

    # Mock the get_entity method to return None
    hass.data[DOMAIN].get_entity = lambda entity_id: None

    # Try to add item in a list that exists but get_entity returns None
    with pytest.raises(intent.IntentHandleError, match="No to-do list: List 1"):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_ADD_ITEM,
            {
                "item": {"value": "wine"},
                "name": {"value": "List 1"},
            },
            assistant=conversation.DOMAIN,
        )


async def test_complete_item_intent(
    hass: HomeAssistant,
) -> None:
    """Test the complete item intent."""
    entity1 = MockTodoListEntity(
        [
            TodoItem(
                summary="Beer",
                uid="1",
                status=TodoItemStatus.NEEDS_ACTION,
                description="Belgian",
                due=dt.date(2026, 11, 20),
            ),
            TodoItem(summary="Wine", uid="2", status=TodoItemStatus.NEEDS_ACTION),
        ]
    )
    entity1._attr_name = "List 1"
    entity1.entity_id = "todo.list_1"

    # Add entities to hass
    config_entry = await create_mock_platform(hass, [entity1])
    assert config_entry.state is ConfigEntryState.LOADED

    assert len(entity1.items) == 2
    assert entity1.items[0].status == TodoItemStatus.NEEDS_ACTION

    # Complete item
    async_mock_service(hass, DOMAIN, todo_intent.INTENT_LIST_COMPLETE_ITEM)
    response = await intent.async_handle(
        hass,
        DOMAIN,
        todo_intent.INTENT_LIST_COMPLETE_ITEM,
        {"item": {"value": "beer"}, "name": {"value": "list 1"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 2
    assert entity1.items[0].status == TodoItemStatus.COMPLETED
    # Completing an item keeps its other fields
    assert entity1.items[0].description == "Belgian"
    assert entity1.items[0].due == dt.date(2026, 11, 20)


async def test_complete_item_intent_errors(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test errors with the complete item intent."""
    entity1 = MockTodoListEntity(
        [
            TodoItem(summary="beer", uid="1", status=TodoItemStatus.COMPLETED),
        ]
    )
    entity1._attr_name = "List 1"
    entity1.entity_id = "todo.list_1"

    # Add entities to hass
    await create_mock_platform(hass, [entity1])

    # Try to complete item in list that does not exist
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_COMPLETE_ITEM,
            {
                "item": {"value": "wine"},
                "name": {"value": "This list does not exist"},
            },
            assistant=conversation.DOMAIN,
        )

    # Try to complete item that does not exist
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_COMPLETE_ITEM,
            {"item": {"value": "bread"}, "name": {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        )

    # Item is already completed
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_COMPLETE_ITEM,
            {"item": {"value": "beer"}, "name": {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        )


async def test_complete_item_intent_ha_errors(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test error handling of HA errors with the complete item intent."""
    test_entity._attr_name = "List 1"
    test_entity.entity_id = "todo.list_1"
    await create_mock_platform(hass, [test_entity])

    # Mock the get_entity method to return None
    with (
        patch(
            "homeassistant.helpers.entity_component.EntityComponent.get_entity",
            return_value=None,
        ),
        pytest.raises(intent.IntentHandleError),
    ):
        await intent.async_handle(
            hass,
            DOMAIN,
            todo_intent.INTENT_LIST_COMPLETE_ITEM,
            {"item": {"value": "wine"}, "name": {"value": "List 1"}},
            assistant=conversation.DOMAIN,
        )


async def test_remove_item_intent(
    hass: HomeAssistant,
) -> None:
    """Test the remove item intent."""
    entity1 = MockTodoListEntity(
        [
            TodoItem(summary="Beer", uid="1", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="wine", uid="2", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="beer", uid="3", status=TodoItemStatus.COMPLETED),
        ]
    )
    entity1._attr_name = "List 1"
    entity1.entity_id = "todo.list_1"

    # Add entities to hass
    config_entry = await create_mock_platform(hass, [entity1])
    assert config_entry.state is ConfigEntryState.LOADED

    assert len(entity1.items) == 3

    # Remove item
    async_mock_service(hass, DOMAIN, todo_intent.INTENT_LIST_REMOVE_ITEM)
    response = await intent.async_handle(
        hass,
        DOMAIN,
        todo_intent.INTENT_LIST_REMOVE_ITEM,
        {"item": {"value": "beer"}, "name": {"value": "list 1"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE

    # only the first matching item has been removed
    assert len(entity1.items) == 2
    assert entity1.items[0].uid == "2"
    assert entity1.items[1].uid == "3"


async def test_remove_item_intent_errors(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test errors with the remove item intent."""
    entity1 = MockTodoListEntity(
        [
            TodoItem(summary="beer", uid="1", status=TodoItemStatus.COMPLETED),
        ]
    )
    entity1._attr_name = "List 1"
    entity1.entity_id = "todo.list_1"

    # Add entities to hass
    await create_mock_platform(hass, [entity1])

    # Try to remove item in list that does not exist
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_REMOVE_ITEM,
            {
                "item": {"value": "wine"},
                "name": {"value": "This list does not exist"},
            },
            assistant=conversation.DOMAIN,
        )

    # Try to remove item that does not exist
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_REMOVE_ITEM,
            {"item": {"value": "bread"}, "name": {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        )


async def test_complete_item_intent_waits_while_parent_is_set(
    hass: HomeAssistant,
) -> None:
    """Test completing an item doesn't write back a parent changed meanwhile."""
    entity = MockTodoListEntity(
        [
            TodoItem(summary="P", uid="p", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(
                summary="A", uid="a", status=TodoItemStatus.NEEDS_ACTION, parent_uid="p"
            ),
        ]
    )
    entity._attr_name = "List 1"
    entity.entity_id = "todo.list_1"
    entity._attr_supported_features = (
        TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.SET_PARENT_ON_ITEM
    )
    reached, saved = asyncio.Event(), asyncio.Event()
    update = entity.async_update_todo_item

    async def save(item: TodoItem) -> None:
        if item.status != TodoItemStatus.COMPLETED:
            reached.set()
            await saved.wait()
        await update(item)

    entity.async_update_todo_item = save
    await create_mock_platform(hass, [entity])

    set_parent = hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            TodoServices.UPDATE_ITEM,
            {TodoServiceArgument.ITEM: "a", TodoServiceArgument.PARENT: ""},
            target={TargetKey.ENTITY_ID: "todo.list_1"},
            blocking=True,
        )
    )
    await reached.wait()
    complete = hass.async_create_task(
        intent.async_handle(
            hass,
            DOMAIN,
            todo_intent.INTENT_LIST_COMPLETE_ITEM,
            {"item": {"value": "A"}, "name": {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        ),
        eager_start=True,
    )
    saved.set()
    async with asyncio.timeout(1):
        await asyncio.gather(set_parent, complete)

    assert {item.uid: (item.parent_uid, item.status) for item in entity.items} == {
        "p": (None, TodoItemStatus.NEEDS_ACTION),
        "a": (None, TodoItemStatus.COMPLETED),
    }
