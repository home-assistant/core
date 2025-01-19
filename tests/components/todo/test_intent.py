"""Tests for the todo intents."""

import pytest

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.todo import (
    ATTR_ITEM,
    DOMAIN,
    TodoItemStatus,
    TodoListEntity,
    intent as todo_intent,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from . import MockTodoListEntity, create_mock_platform

from tests.typing import WebSocketGenerator


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
        {ATTR_ITEM: {"value": " beer "}, "name": {"value": "list 1"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.success_results[0].name == "list 1"
    assert response.success_results[0].type == intent.IntentResponseTargetType.ENTITY
    assert response.success_results[0].id == entity1.entity_id

    assert len(entity1.items) == 1
    assert len(entity2.items) == 0
    assert entity1.items[0].summary == "beer"  # summary is trimmed
    assert entity1.items[0].status == TodoItemStatus.NEEDS_ACTION
    entity1.items.clear()

    # Add to second list
    response = await intent.async_handle(
        hass,
        "test",
        todo_intent.INTENT_LIST_ADD_ITEM,
        {ATTR_ITEM: {"value": "cheese"}, "name": {"value": "List 2"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 0
    assert len(entity2.items) == 1
    assert entity2.items[0].summary == "cheese"
    assert entity2.items[0].status == TodoItemStatus.NEEDS_ACTION

    # List name is case insensitive
    response = await intent.async_handle(
        hass,
        "test",
        todo_intent.INTENT_LIST_ADD_ITEM,
        {ATTR_ITEM: {"value": "wine"}, "name": {"value": "lIST 2"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 0
    assert len(entity2.items) == 2
    assert entity2.items[1].summary == "wine"
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
    assert err.value.result.no_match_reason == intent.MatchFailedReason.ASSISTANT

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
                ATTR_ITEM: {"value": "wine"},
                ATTR_NAME: {"value": "This list does not exist"},
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
                ATTR_ITEM: {"value": "wine"},
                ATTR_NAME: {"value": "List 1"},
            },
            assistant=conversation.DOMAIN,
        )
