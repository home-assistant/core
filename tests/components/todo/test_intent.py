"""Tests for the todo intents."""

import pytest

from homeassistant.components import conversation
from homeassistant.components.todo import (
    ATTR_ITEM,
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    intent as todo_intent,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from . import MockTodoListEntity, create_mock_platform

from tests.common import async_mock_service


@pytest.fixture(autouse=True)
async def setup_intents(hass: HomeAssistant) -> None:
    """Set up the intents."""
    assert await async_setup_component(hass, "homeassistant", {})
    await todo_intent.async_setup_intents(hass)


async def test_remove_item_intent(
    hass: HomeAssistant,
) -> None:
    """Test removing items from lists using an intent."""
    entity1 = MockTodoListEntity(
        [
            TodoItem(summary="beer", uid="1", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="wine", uid="2", status=TodoItemStatus.NEEDS_ACTION),
        ]
    )
    entity1._attr_name = "List 1"
    entity1.entity_id = "todo.list_1"

    entity2 = MockTodoListEntity(
        [TodoItem(summary="cheese", uid="3", status=TodoItemStatus.NEEDS_ACTION)]
    )
    entity2._attr_name = "List 2"
    entity2.entity_id = "todo.list_2"

    # Add entities to hass
    config_entry = await create_mock_platform(hass, [entity1, entity2])
    assert config_entry.state is ConfigEntryState.LOADED

    assert len(entity1.items) == 2
    assert len(entity2.items) == 1

    # Remove from first list
    async_mock_service(hass, DOMAIN, todo_intent.INTENT_LIST_REMOVE_ITEM)
    response = await intent.async_handle(
        hass,
        DOMAIN,
        todo_intent.INTENT_LIST_REMOVE_ITEM,
        {ATTR_ITEM: {"value": "beer"}, ATTR_NAME: {"value": "list 1"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 1
    assert entity1.items[0].summary == "wine"
    assert len(entity2.items) == 1

    # Remove from second list
    response = await intent.async_handle(
        hass,
        "test",
        todo_intent.INTENT_LIST_REMOVE_ITEM,
        {ATTR_ITEM: {"value": "cheese"}, ATTR_NAME: {"value": "List 2"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 1
    assert len(entity2.items) == 0

    # Try to remove non-existent item
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_REMOVE_ITEM,
            {ATTR_ITEM: {"value": "bread"}, ATTR_NAME: {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        )

    # Try to remove from non-existent list
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_REMOVE_ITEM,
            {
                ATTR_ITEM: {"value": "wine"},
                ATTR_NAME: {"value": "This list does not exist"},
            },
            assistant=conversation.DOMAIN,
        )
