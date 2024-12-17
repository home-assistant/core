"""Tests for Habitica todo platform."""

from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import UUID

from habiticalib import Direction, HabiticaTasksResponse, Task, TaskType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import DOMAIN
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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import ERROR_NOT_FOUND

from tests.common import (
    MockConfigEntry,
    async_get_persistent_notifications,
    load_fixture,
    snapshot_platform,
)
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def todo_only() -> Generator[None]:
    """Enable only the todo platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.TODO],
    ):
        yield


@pytest.mark.usefixtures("habitica")
async def test_todos(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test todo platform."""

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
@pytest.mark.usefixtures("habitica")
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


@pytest.mark.freeze_time("2024-09-21 00:00:00")
@pytest.mark.parametrize(
    ("entity_id", "uid"),
    [
        ("todo.test_user_to_do_s", "88de7cd9-af2b-49ce-9afd-bf941d87336b"),
        ("todo.test_user_dailies", "f2c85972-1a19-4426-bc6d-ce3337b9d99f"),
    ],
    ids=["todo", "daily"],
)
async def test_complete_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
    uid: str,
) -> None:
    """Test completing an item on the todo list."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: uid, ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    habitica.update_score.assert_awaited_once_with(UUID(uid), Direction.UP)

    # Test notification for item drop
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    _id, *_ = notifications
    assert snapshot == (notifications[_id]["title"], notifications[_id]["message"])


@pytest.mark.parametrize(
    ("entity_id", "uid"),
    [
        ("todo.test_user_to_do_s", "162f0bbe-a097-4a06-b4f4-8fbeed85d2ba"),
        ("todo.test_user_dailies", "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"),
    ],
    ids=["todo", "daily"],
)
async def test_uncomplete_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    entity_id: str,
    uid: str,
) -> None:
    """Test uncompleting an item on the todo list."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: uid, ATTR_STATUS: "needs_action"},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    habitica.update_score.assert_called_once_with(UUID(uid), Direction.DOWN)


@pytest.mark.parametrize(
    ("uid", "status"),
    [
        ("88de7cd9-af2b-49ce-9afd-bf941d87336b", "completed"),
        ("162f0bbe-a097-4a06-b4f4-8fbeed85d2ba", "needs_action"),
    ],
    ids=["completed", "needs_action"],
)
async def test_complete_todo_item_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    uid: str,
    status: str,
) -> None:
    """Test exception when completing/uncompleting an item on the todo list."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    habitica.update_score.side_effect = ERROR_NOT_FOUND
    with pytest.raises(
        expected_exception=ServiceValidationError,
        match=r"Unable to update the score for your Habitica to-do `.+`, please try again",
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: uid, ATTR_STATUS: status},
            target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_id", "uid", "date"),
    [
        (
            "todo.test_user_to_do_s",
            "88de7cd9-af2b-49ce-9afd-bf941d87336b",
            date(day=30, month=7, year=2024),
        ),
        (
            "todo.test_user_dailies",
            "f2c85972-1a19-4426-bc6d-ce3337b9d99f",
            None,
        ),
    ],
    ids=["todo", "daily"],
)
async def test_update_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    entity_id: str,
    uid: str,
    date: date | None,
) -> None:
    """Test update details of a item on the todo list."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ITEM: uid,
            ATTR_RENAME: "test-summary",
            ATTR_DESCRIPTION: "test-description",
            ATTR_DUE_DATE: date,
        },
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    task = Task(
        notes="test-description",
        text="test-summary",
    )
    if date:
        task["date"] = date
    habitica.update_task.assert_awaited_once_with(UUID(uid), task)


async def test_update_todo_item_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test exception when update item on the todo list."""
    uid = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # mock_habitica.put(
    #     f"{DEFAULT_URL}/api/v3/tasks/{uid}",
    #     status=HTTPStatus.NOT_FOUND,
    # )
    habitica.update_task.side_effect = ERROR_NOT_FOUND
    with pytest.raises(
        expected_exception=ServiceValidationError,
        match="Unable to update the Habitica to-do `test-summary`, please try again",
    ):
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


async def test_add_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test add a todo item to the todo list."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

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

    habitica.create_task.assert_awaited_once_with(
        Task(
            date=date(day=30, month=7, year=2024),
            notes="test-description",
            text="test-summary",
            type=TaskType.TODO,
        )
    )


async def test_add_todo_item_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test exception when adding a todo item to the todo list."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    habitica.create_task.side_effect = ERROR_NOT_FOUND
    with pytest.raises(
        expected_exception=ServiceValidationError,
        match="Unable to create new to-do `test-summary` for Habitica, please try again",
    ):
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


async def test_delete_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test deleting a todo item from the todo list."""

    uid = "2f6fcabc-f670-4ec3-ba65-817e8deea490"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: uid},
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    habitica.delete_task.assert_awaited_once_with(UUID(uid))


async def test_delete_todo_item_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test exception when deleting a todo item from the todo list."""

    uid = "2f6fcabc-f670-4ec3-ba65-817e8deea490"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    habitica.delete_task.side_effect = ERROR_NOT_FOUND

    with pytest.raises(
        expected_exception=ServiceValidationError,
        match="Unable to delete item from Habitica to-do list, please try again",
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: uid},
            target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
            blocking=True,
        )


async def test_delete_completed_todo_items(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test deleting completed todo items from the todo list."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_COMPLETED_ITEMS,
        {},
        target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
        blocking=True,
    )

    habitica.delete_completed_todos.assert_awaited_once()


async def test_delete_completed_todo_items_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test exception when deleting completed todo items from the todo list."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    habitica.delete_completed_todos.side_effect = ERROR_NOT_FOUND
    with pytest.raises(
        expected_exception=ServiceValidationError,
        match="Unable to delete completed to-do items from Habitica to-do list, please try again",
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_COMPLETED_ITEMS,
            {},
            target={ATTR_ENTITY_ID: "todo.test_user_to_do_s"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_id", "uid", "previous_uid"),
    [
        (
            "todo.test_user_to_do_s",
            "1aa3137e-ef72-4d1f-91ee-41933602f438",
            "88de7cd9-af2b-49ce-9afd-bf941d87336b",
        ),
        (
            "todo.test_user_dailies",
            "2c6d136c-a1c3-4bef-b7c4-fa980784b1e1",
            "564b9ac9-c53d-4638-9e7f-1cd96fe19baa",
        ),
    ],
    ids=["todo", "daily"],
)
async def test_move_todo_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    uid: str,
    previous_uid: str,
) -> None:
    """Test move todo items."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_ws_client()
    # move to second position
    data = {
        "id": id,
        "type": "todo/item/move",
        "entity_id": entity_id,
        "uid": uid,
        "previous_uid": previous_uid,
    }
    await client.send_json_auto_id(data)
    resp = await client.receive_json()
    assert resp.get("success")

    habitica.reorder_task.assert_awaited_once_with(UUID(uid), 1)
    habitica.reorder_task.reset_mock()

    # move to top position
    data = {
        "id": id,
        "type": "todo/item/move",
        "entity_id": entity_id,
        "uid": uid,
    }
    await client.send_json_auto_id(data)
    resp = await client.receive_json()
    assert resp.get("success")

    habitica.reorder_task.assert_awaited_once_with(UUID(uid), 0)


async def test_move_todo_item_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test exception when moving todo item."""

    uid = "1aa3137e-ef72-4d1f-91ee-41933602f438"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    habitica.reorder_task.side_effect = ERROR_NOT_FOUND
    client = await hass_ws_client()

    data = {
        "id": id,
        "type": "todo/item/move",
        "entity_id": "todo.test_user_to_do_s",
        "uid": uid,
    }
    await client.send_json_auto_id(data)

    resp = await client.receive_json()
    habitica.reorder_task.assert_awaited_once_with(UUID(uid), 0)

    assert resp["success"] is False
    assert (
        resp["error"]["message"]
        == "Unable to move the Habitica to-do to position 0, please try again"
    )


@pytest.mark.parametrize(
    ("fixture", "calculated_due_date"),
    [
        ("duedate_fixture_1.json", "2024-09-22"),
        ("duedate_fixture_2.json", "2024-09-24"),
        ("duedate_fixture_3.json", "2024-10-23"),
        ("duedate_fixture_4.json", "2024-10-23"),
        ("duedate_fixture_5.json", "2024-09-28"),
        ("duedate_fixture_6.json", "2024-10-21"),
        ("duedate_fixture_7.json", None),
        ("duedate_fixture_8.json", None),
    ],
    ids=[
        "default",
        "daily starts on startdate",
        "monthly starts on startdate",
        "yearly starts on startdate",
        "weekly",
        "monthly starts on fixed day",
        "grey daily",
        "empty nextDue",
    ],
)
@pytest.mark.usefixtures("set_tz")
async def test_next_due_date(
    hass: HomeAssistant,
    fixture: str,
    calculated_due_date: str | None,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test next_due_date calculation."""

    dailies_entity = "todo.test_user_dailies"

    habitica.get_tasks.side_effect = [
        HabiticaTasksResponse.from_json(load_fixture(fixture, DOMAIN)),
        HabiticaTasksResponse.from_dict({"success": True, "data": []}),
    ]

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: dailies_entity},
        blocking=True,
        return_response=True,
    )

    assert result[dailies_entity]["items"][0].get("due") == calculated_due_date
