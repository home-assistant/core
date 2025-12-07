"""Unit tests for the Todoist todo platform."""

import datetime
from typing import Any
from unittest.mock import AsyncMock
import zoneinfo

import pytest
from todoist_api_python.models import Due, Task

from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_DUE_DATE,
    ATTR_DUE_DATETIME,
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.components.todoist.todo import define_priority_level
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import PROJECT_ID, make_api_task

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.TODO]


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant) -> None:
    """Set the time zone for the tests that keesp UTC-6 all year round."""
    await hass.config.async_set_time_zone("America/Regina")


@pytest.mark.parametrize(
    ("tasks", "expected_state"),
    [
        ([], "0"),
        ([make_api_task(id="12345", content="Soda", is_completed=False)], "1"),
        ([make_api_task(id="12345", content="Soda", is_completed=True)], "0"),
        (
            [
                make_api_task(id="12345", content="Milk", is_completed=False),
                make_api_task(id="54321", content="Soda", is_completed=False),
            ],
            "2",
        ),
        (
            [
                make_api_task(
                    id="12345",
                    content="Soda",
                    is_completed=False,
                    project_id="other-project-id",
                )
            ],
            "0",
        ),
        (
            [
                make_api_task(
                    id="12345", content="sub-task", is_completed=False, parent_id="1"
                )
            ],
            "0",
        ),
    ],
)
async def test_todo_item_state(
    hass: HomeAssistant,
    setup_integration: None,
    expected_state: str,
) -> None:
    """Test for a To-do List entity state."""

    state = hass.states.get("todo.name")
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("tasks", "item_data", "tasks_after_update", "add_kwargs", "expected_item"),
    [
        (
            [],
            {},
            [make_api_task(id="task-id-1", content="Soda", is_completed=False)],
            {"content": "Soda", "due_string": "no date", "description": ""},
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "priority": "Low",
            },
        ),
        (
            [],
            {ATTR_DUE_DATE: "2023-11-18"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    is_completed=False,
                    due=Due(is_recurring=False, date="2023-11-18", string="today"),
                )
            ],
            {"description": "", "due_date": datetime.date(2023, 11, 18)},
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "due": "2023-11-18",
                "priority": "Low",
            },
        ),
        (
            [],
            {ATTR_DUE_DATETIME: "2023-11-18T06:30:00"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    is_completed=False,
                    due=Due(
                        date="2023-11-18",
                        is_recurring=False,
                        string="today",
                    ),
                )
            ],
            {
                "description": "",
                "due_datetime": datetime.datetime(
                    2023, 11, 18, 6, 30, tzinfo=zoneinfo.ZoneInfo("America/Regina")
                ),
            },
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "due": "2023-11-18",
                "priority": "Low",
            },
        ),
        (
            [],
            {ATTR_DESCRIPTION: "6-pack"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    description="6-pack",
                    is_completed=False,
                )
            ],
            {"description": "6-pack", "due_string": "no date"},
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "description": "6-pack",
                "priority": "Low",
            },
        ),
    ],
    ids=["summary", "due_date", "due_datetime", "description"],
)
async def test_add_todo_list_item(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
    item_data: dict[str, Any],
    tasks_after_update: list[Task],
    add_kwargs: dict[str, Any],
    expected_item: dict[str, Any],
) -> None:
    """Test for adding a To-do Item."""

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "0"

    api.add_task = AsyncMock()

    async def fake_gen():
        yield tasks_after_update

    api.get_tasks.side_effect = fake_gen

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Soda", **item_data},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
    )

    args = api.add_task.call_args
    assert args
    assert args.kwargs == {"project_id": PROJECT_ID, "content": "Soda", **add_kwargs}

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "1"

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
        return_response=True,
    )
    assert result == {"todo.name": {"items": [expected_item]}}


@pytest.mark.parametrize(
    ("tasks"), [[make_api_task(id="task-id-1", content="Soda", is_completed=False)]]
)
async def test_update_todo_item_status(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
) -> None:
    """Test for updating a To-do Item that changes the status."""

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "1"

    api.complete_task = AsyncMock()
    api.uncomplete_task = AsyncMock()

    async def fake_get_tasks():
        yield [make_api_task(id="task-id-1", content="Soda", is_completed=True)]

    api.get_tasks.side_effect = fake_get_tasks

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "task-id-1", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
    )
    assert api.complete_task.called
    args = api.complete_task.call_args
    assert args
    assert args.kwargs.get("task_id") == "task-id-1"
    assert not api.uncomplete_task.called

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "0"

    async def fake_get_tasks2():
        yield [make_api_task(id="task-id-1", content="Soda", is_completed=False)]

    api.get_tasks.side_effect = fake_get_tasks2

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "task-id-1", ATTR_STATUS: "needs_action"},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
    )
    assert api.uncomplete_task.called
    args = api.uncomplete_task.call_args
    assert args
    assert args.kwargs.get("task_id") == "task-id-1"

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    ("tasks", "update_data", "tasks_after_update", "update_kwargs", "expected_item"),
    [
        (
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    is_completed=False,
                    description="desc",
                )
            ],
            {ATTR_RENAME: "Milk"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Milk",
                    is_completed=False,
                    description="desc",
                )
            ],
            {
                "task_id": "task-id-1",
                "content": "Milk",
                "description": "desc",
                "due_string": "no date",
            },
            {
                "uid": "task-id-1",
                "summary": "Milk",
                "status": "needs_action",
                "description": "desc",
                "priority": "Low",
            },
        ),
        (
            [make_api_task(id="task-id-1", content="Soda", is_completed=False)],
            {ATTR_DUE_DATE: "2023-11-18"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    is_completed=False,
                    due=Due(is_recurring=False, date="2023-11-18", string="today"),
                )
            ],
            {
                "task_id": "task-id-1",
                "content": "Soda",
                "due_date": datetime.date(2023, 11, 18),
                "description": "",
            },
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "due": "2023-11-18",
                "priority": "Low",
            },
        ),
        (
            [make_api_task(id="task-id-1", content="Soda", is_completed=False)],
            {ATTR_DUE_DATETIME: "2023-11-18T06:30:00"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    is_completed=False,
                    due=Due(
                        date="2023-11-18",
                        is_recurring=False,
                        string="today",
                    ),
                )
            ],
            {
                "task_id": "task-id-1",
                "content": "Soda",
                "due_datetime": datetime.datetime(
                    2023, 11, 18, 6, 30, tzinfo=zoneinfo.ZoneInfo("America/Regina")
                ),
                "description": "",
            },
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "due": "2023-11-18",
                "priority": "Low",
            },
        ),
        (
            [make_api_task(id="task-id-1", content="Soda", is_completed=False)],
            {ATTR_DESCRIPTION: "6-pack"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    description="6-pack",
                    is_completed=False,
                )
            ],
            {
                "task_id": "task-id-1",
                "content": "Soda",
                "description": "6-pack",
                "due_string": "no date",
            },
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "description": "6-pack",
                "priority": "Low",
            },
        ),
        (
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    description="6-pack",
                    is_completed=False,
                )
            ],
            {ATTR_DESCRIPTION: None},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    is_completed=False,
                    description="",
                )
            ],
            {
                "task_id": "task-id-1",
                "content": "Soda",
                "description": "",
                "due_string": "no date",
            },
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "priority": "Low",
            },
        ),
        (
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    description="6-pack",
                    is_completed=False,
                    due=Due(date="2024-01-01", is_recurring=True, string="every day"),
                )
            ],
            {ATTR_DUE_DATE: "2024-02-01"},
            [
                make_api_task(
                    id="task-id-1",
                    content="Soda",
                    description="6-pack",
                    is_completed=False,
                    due=Due(date="2024-02-01", is_recurring=True, string="every day"),
                )
            ],
            {
                "task_id": "task-id-1",
                "content": "Soda",
                "description": "6-pack",
                "due_date": datetime.date(2024, 2, 1),
                "due_string": "every day",
            },
            {
                "uid": "task-id-1",
                "summary": "Soda",
                "status": "needs_action",
                "description": "6-pack",
                "due": "2024-02-01",
                "priority": "Low",
            },
        ),
    ],
    ids=[
        "rename",
        "due_date",
        "due_datetime",
        "description",
        "clear_description",
        "due_date_with_recurrence",
    ],
)
async def test_update_todo_items(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
    update_data: dict[str, Any],
    tasks_after_update: list[Task],
    update_kwargs: dict[str, Any],
    expected_item: dict[str, Any],
) -> None:
    """Test for updating a To-do Item that changes the summary."""

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "1"

    api.update_task = AsyncMock()

    async def fake_gen():
        yield tasks_after_update

    api.get_tasks.side_effect = fake_gen

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "task-id-1", **update_data},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
    )
    assert api.update_task.called
    args = api.update_task.call_args
    assert args
    assert args.kwargs == update_kwargs

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
        return_response=True,
    )
    assert result == {"todo.name": {"items": [expected_item]}}


@pytest.mark.parametrize(
    ("tasks"),
    [
        [
            make_api_task(id="task-id-1", content="Soda", is_completed=False),
            make_api_task(id="task-id-2", content="Milk", is_completed=False),
        ]
    ],
)
async def test_remove_todo_item(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
) -> None:
    """Test for removing a To-do Item."""

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "2"

    api.delete_task = AsyncMock()

    async def fake_get_tasks_empty():
        yield []

    api.get_tasks.side_effect = fake_get_tasks_empty

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: ["task-id-1", "task-id-2"]},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
    )
    assert api.delete_task.call_count == 2
    args = api.delete_task.call_args_list
    assert args[0].kwargs.get("task_id") == "task-id-1"
    assert args[1].kwargs.get("task_id") == "task-id-2"

    await async_update_entity(hass, "todo.name")
    state = hass.states.get("todo.name")
    assert state
    assert state.state == "0"


@pytest.mark.parametrize(
    ("tasks"), [[make_api_task(id="task-id-1", content="Cheese", is_completed=False)]]
)
async def test_subscribe(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test for subscribing to state updates."""

    # Subscribe and get the initial list
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/subscribe",
            "entity_id": "todo.name",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None
    subscription_id = msg["id"]

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    items = msg["event"].get("items")
    assert items
    assert len(items) == 1
    assert items[0]["summary"] == "Cheese"
    assert items[0]["status"] == "needs_action"
    assert items[0]["uid"]

    async def fake_get_tasks():
        yield [make_api_task(id="test-id-1", content="Wine", is_completed=False)]

    api.get_tasks.side_effect = fake_get_tasks

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "Cheese", ATTR_RENAME: "Wine"},
        target={ATTR_ENTITY_ID: "todo.name"},
        blocking=True,
    )

    # Verify update is published
    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    items = msg["event"].get("items")
    assert items
    assert len(items) == 1
    assert items[0]["summary"] == "Wine"
    assert items[0]["status"] == "needs_action"
    assert items[0]["uid"]


@pytest.mark.parametrize(
    ("priority", "expected"),
    [
        # Positive scenarios
        (1, "Low"),
        (2, "Medium"),
        (3, "High"),
        (4, "Urgent"),
        # Negative / invalid scenarios
        (0, "Unknown"),
        (5, "Unknown"),
        (-1, "Unknown"),
        ("3", "Unknown"),
        (None, "Unknown"),
        (2.5, "Unknown"),
    ],
)
def test_define_priority_level(priority, expected) -> None:
    """Test that define_priority_level maps priorities to the expected labels."""
    assert define_priority_level(priority) == expected
