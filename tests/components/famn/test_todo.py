"""Tests for the Famn todo platform."""

import re
from unittest.mock import AsyncMock

from famn_sdk import ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_ITEM,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CHORES_LIST_ID, SHOPPING_LIST_ID, TODOS_LIST_ID

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "todo.home_assistant_weekly_chores"
TODOS_ENTITY_ID = "todo.home_assistant_todos"
SHOPPING_ENTITY_ID = "todo.home_assistant_handleliste"

pytestmark = [pytest.mark.usefixtures("mock_famn")]


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the todo entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_todo_items(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the open chores exposed by a Famn chore list."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "2"

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    items = result[ENTITY_ID]["items"]
    assert [item["summary"] for item in items] == [
        "Take out the trash",
        "Vacuum the living room",
    ]
    assert all(item["status"] == "needs_action" for item in items)


async def test_complete_item(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
) -> None:
    """Test marking a chore as done."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_ITEM: "Take out the trash",
            ATTR_STATUS: "completed",
        },
        blocking=True,
    )

    mock_tasks_api.log_task_item_done_endpoint.assert_called_once_with(
        "8c7f0a11-3d2e-4c5b-9a8f-1b2c3d4e5001", CHORES_LIST_ID
    )


async def test_complete_item_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
) -> None:
    """Test that a failing request surfaces as a Home Assistant error."""
    await setup_integration(hass, mock_config_entry)
    mock_tasks_api.log_task_item_done_endpoint.side_effect = ApiError(500, "boom")

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Failed to mark Take out the trash as done in Famn"),
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_ITEM: "Take out the trash",
                ATTR_STATUS: "completed",
            },
            blocking=True,
        )


async def test_create_todo_item(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
) -> None:
    """Test creating a todo from an automation-style service call."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ENTITY_ID: TODOS_ENTITY_ID,
            ATTR_ITEM: "Empty the washing machine",
            ATTR_DESCRIPTION: "The wash cycle finished",
        },
        blocking=True,
    )

    call = mock_tasks_api.create_task_item_endpoint.call_args
    assert call.args[0] == TODOS_LIST_ID
    assert call.kwargs["body"].title == "Empty the washing machine"
    assert call.kwargs["body"].description == "The wash cycle finished"
    assert call.kwargs["body"].task_list_id == TODOS_LIST_ID


async def test_create_todo_item_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
) -> None:
    """Test that a failing create surfaces as a Home Assistant error."""
    await setup_integration(hass, mock_config_entry)
    mock_tasks_api.create_task_item_endpoint.side_effect = ApiError(500, "boom")

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Failed to create Empty the washing machine in Famn"),
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {
                ATTR_ENTITY_ID: TODOS_ENTITY_ID,
                ATTR_ITEM: "Empty the washing machine",
            },
            blocking=True,
        )


async def test_create_not_supported_on_chore_lists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
) -> None:
    """Test that chore lists reject creating items."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_ITEM: "Not allowed",
            },
            blocking=True,
        )
    mock_tasks_api.create_task_item_endpoint.assert_not_called()


async def test_shopping_list_items(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the open items exposed by a Famn shopping list."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SHOPPING_ENTITY_ID)
    assert state is not None
    assert state.state == "2"

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: SHOPPING_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    items = result[SHOPPING_ENTITY_ID]["items"]
    assert [item["summary"] for item in items] == ["Melk", "Brød"]


async def test_shopping_add_item(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_api: AsyncMock,
) -> None:
    """Test adding an item to the shopping list, as Assist would."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ENTITY_ID: SHOPPING_ENTITY_ID,
            ATTR_ITEM: "Tacokrydder",
        },
        blocking=True,
    )

    call = mock_list_api.create_list_item_endpoint.call_args
    assert call.args[0] == SHOPPING_LIST_ID
    assert call.kwargs["body"].name == "Tacokrydder"
    assert str(call.kwargs["body"].list_id) == SHOPPING_LIST_ID
    assert call.kwargs["combine_same_items"] is True


async def test_shopping_check_off_item(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_api: AsyncMock,
) -> None:
    """Test checking an item off the shopping list."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: SHOPPING_ENTITY_ID,
            ATTR_ITEM: "Melk",
            ATTR_STATUS: "completed",
        },
        blocking=True,
    )

    mock_list_api.set_list_item_done_endpoint.assert_called_once_with(
        SHOPPING_LIST_ID, "7c6d5e4f-3a2b-4c1d-9e8f-7a6b5c4d3001"
    )


async def test_shopping_uncheck_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_api: AsyncMock,
) -> None:
    """Test that re-opening a checked item is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {
                ATTR_ENTITY_ID: SHOPPING_ENTITY_ID,
                ATTR_ITEM: "Melk",
                ATTR_STATUS: "needs_action",
            },
            blocking=True,
        )
    mock_list_api.set_list_item_done_endpoint.assert_not_called()


async def test_uncomplete_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tasks_api: AsyncMock,
) -> None:
    """Test that re-opening a chore is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_ITEM: "Take out the trash",
                ATTR_STATUS: "needs_action",
            },
            blocking=True,
        )
    mock_tasks_api.log_task_item_done_endpoint.assert_not_called()
