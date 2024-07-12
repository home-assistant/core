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


async def test_score_up_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test completing an item on the todo list."""
    uid = "77777777-7777-7777-7777-777777777777"
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


async def test_score_down_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test uncompleting an item on the todo list."""
    uid = "10101010-1010-1010-1010-101010101010"
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
    uid = "77777777-7777-7777-7777-777777777777"
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
    uid = "10101010-1010-1010-1010-101010101010"
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


@pytest.mark.usefixtures("mock_habitica")
async def test_get_todo_items(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test deleting completed todo items from the todo list."""
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
