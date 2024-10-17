"""Tests for the todo intents."""

from unittest.mock import patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.todo import (
    ATTR_ITEM,
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
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


async def test_complete_item_intent(
    hass: HomeAssistant,
) -> None:
    """Test the complete item intent."""
    entity1 = MockTodoListEntity(
        [
            TodoItem(summary="beer", uid="1", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="wine", uid="2", status=TodoItemStatus.NEEDS_ACTION),
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
        {ATTR_ITEM: {"value": "beer"}, ATTR_NAME: {"value": "list 1"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 2
    assert entity1.items[0].status == TodoItemStatus.COMPLETED


async def test_complete_item_intent_errors(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test errors with the complete item intent."""
    test_entity._attr_name = "List 1"
    await create_mock_platform(hass, [test_entity])

    # Try to complete item in list that does not exist
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_COMPLETE_ITEM,
            {
                ATTR_ITEM: {"value": "wine"},
                ATTR_NAME: {"value": "This list does not exist"},
            },
            assistant=conversation.DOMAIN,
        )

    # Try to complete item that does not exist
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_COMPLETE_ITEM,
            {ATTR_ITEM: {"value": "bread"}, ATTR_NAME: {"value": "list 1"}},
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
            {ATTR_ITEM: {"value": "wine"}, ATTR_NAME: {"value": "List 1"}},
            assistant=conversation.DOMAIN,
        )
