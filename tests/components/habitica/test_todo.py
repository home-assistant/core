"""Tests for Habitica todo platform."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import DEFAULT_URL
from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_DUE_DATE,
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import assert_mock_called_with

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def switch_only() -> Generator[None]:
    """Enable only the todo platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.TODO],
    ):
        yield


@pytest.mark.usefixtures("mock_habitica")
async def test_todos(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test todo entities."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id"),
    [
        "todo.test_user_to_do_s",
        "todo.test_user_dailies",
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_todo_items(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test items on todo lists."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
        return_response=True,
    )

    assert result == snapshot


async def test_complete_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test completing an item on the todo list."""
    uid = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tasks/{uid}/score/up",
        json={"data": {}, "success": True},
    )
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{uid}",
        json={"data": {}, "success": True},
    )
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: uid, ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    assert_mock_called_with(
        mock_habitica, "post", f"{DEFAULT_URL}/api/v3/tasks/{uid}/score/up"
    )


async def test_uncomplete_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test uncompleting an item on the todo list."""
    uid = "162f0bbe-a097-4a06-b4f4-8fbeed85d2ba"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tasks/{uid}/score/down",
        json={"data": {}, "success": True},
    )
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{uid}",
        json={"data": {}, "success": True},
    )
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: uid, ATTR_STATUS: "needs_action"},
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    assert_mock_called_with(
        mock_habitica, "post", f"{DEFAULT_URL}/api/v3/tasks/{uid}/score/down"
    )


async def test_update_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test update details of a item on the todo list."""
    uid = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{uid}",
        json={"data": {}, "success": True},
    )
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ITEM: uid,
            ATTR_RENAME: "test-summary",
            ATTR_DESCRIPTION: "test-description",
            ATTR_DUE_DATE: "2024-07-30",
        },
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    assert_mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{uid}",
        {
            "date": "2024-07-30",
            "notes": "test-description",
            "text": "test-summary",
        },
    )


async def test_add_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test add a todo item on the todo list."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        json={"data": {}, "success": True},
        status=HTTPStatus.CREATED,
    )
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ITEM: "test-summary",
            ATTR_DESCRIPTION: "test-description",
            ATTR_DUE_DATE: "2024-07-30",
        },
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    assert_mock_called_with(
        mock_habitica,
        "post",
        f"{DEFAULT_URL}/api/v3/tasks/user",
        {
            "date": "2024-07-30",
            "notes": "test-description",
            "text": "test-summary",
            "type": "todo",
        },
    )


async def test_delete_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test deleting a todo item from the todo list."""
    uid = "2f6fcabc-f670-4ec3-ba65-817e8deea490"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.delete(
        f"{DEFAULT_URL}/api/v3/tasks/{uid}",
        json={"data": {}, "success": True},
    )
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: uid},
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    assert_mock_called_with(
        mock_habitica, "delete", f"{DEFAULT_URL}/api/v3/tasks/{uid}"
    )


async def test_delete_completed_todo_items(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test deleting completed todo items from the todo list."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tasks/clearCompletedTodos",
        json={"data": {}, "success": True},
    )
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_COMPLETED_ITEMS,
        {},
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    assert_mock_called_with(
        mock_habitica, "post", f"{DEFAULT_URL}/api/v3/tasks/clearCompletedTodos"
    )


@pytest.mark.usefixtures("mock_habitica")
async def test_get_todo_items(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get todo items from the todo list."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
        return_response=True,
    )

    assert result == snapshot


async def test_move_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get todo items from the todo list."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    for pos in (0, 1):
        mock_habitica.post(
            f"{DEFAULT_URL}/api/v3/tasks/1aa3137e-ef72-4d1f-91ee-41933602f438/move/to/{pos}",
            json={"data": {}, "success": True},
        )

    client = await hass_ws_client()
    # move to second position
    data = {
        "id": id,
        "type": "todo/item/move",
        "entity_id": "todo.test_user_to_do_s",
        "uid": "1aa3137e-ef72-4d1f-91ee-41933602f438",
        "previous_uid": "88de7cd9-af2b-49ce-9afd-bf941d87336b",
    }
    await client.send_json_auto_id(data)
    resp = await client.receive_json()
    assert resp.get("success")

    # move to top position
    data = {
        "id": id,
        "type": "todo/item/move",
        "entity_id": "todo.test_user_to_do_s",
        "uid": "1aa3137e-ef72-4d1f-91ee-41933602f438",
    }
    await client.send_json_auto_id(data)
    resp = await client.receive_json()
    assert resp.get("success")

    for pos in (0, 1):
        assert_mock_called_with(
            mock_habitica,
            "post",
            f"{DEFAULT_URL}/api/v3/tasks/1aa3137e-ef72-4d1f-91ee-41933602f438/move/to/{pos}",
        )
