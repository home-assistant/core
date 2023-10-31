"""Unit tests for the Todoist todo platform."""
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import PROJECT_ID, make_api_task


@pytest.fixture(autouse=True)
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.TODO]


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


@pytest.mark.parametrize(("tasks"), [[]])
async def test_add_todo_list_item(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
) -> None:
    """Test for adding a To-do Item."""

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "0"

    api.add_task = AsyncMock()
    # Fake API response when state is refreshed after create
    api.get_tasks.return_value = [
        make_api_task(id="task-id-1", content="Soda", is_completed=False)
    ]

    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "Soda"},
        target={"entity_id": "todo.name"},
        blocking=True,
    )

    args = api.add_task.call_args
    assert args
    assert args.kwargs.get("content") == "Soda"
    assert args.kwargs.get("project_id") == PROJECT_ID

    # Verify state is refreshed
    state = hass.states.get("todo.name")
    assert state
    assert state.state == "1"


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

    api.close_task = AsyncMock()
    api.reopen_task = AsyncMock()

    # Fake API response when state is refreshed after close
    api.get_tasks.return_value = [
        make_api_task(id="task-id-1", content="Soda", is_completed=True)
    ]

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "task-id-1", "status": "completed"},
        target={"entity_id": "todo.name"},
        blocking=True,
    )
    assert api.close_task.called
    args = api.close_task.call_args
    assert args
    assert args.kwargs.get("task_id") == "task-id-1"
    assert not api.reopen_task.called

    # Verify state is refreshed
    state = hass.states.get("todo.name")
    assert state
    assert state.state == "0"

    # Fake API response when state is refreshed after reopen
    api.get_tasks.return_value = [
        make_api_task(id="task-id-1", content="Soda", is_completed=False)
    ]

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "task-id-1", "status": "needs_action"},
        target={"entity_id": "todo.name"},
        blocking=True,
    )
    assert api.reopen_task.called
    args = api.reopen_task.call_args
    assert args
    assert args.kwargs.get("task_id") == "task-id-1"

    # Verify state is refreshed
    state = hass.states.get("todo.name")
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    ("tasks"), [[make_api_task(id="task-id-1", content="Soda", is_completed=False)]]
)
async def test_update_todo_item_summary(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
) -> None:
    """Test for updating a To-do Item that changes the summary."""

    state = hass.states.get("todo.name")
    assert state
    assert state.state == "1"

    api.update_task = AsyncMock()

    # Fake API response when state is refreshed after close
    api.get_tasks.return_value = [
        make_api_task(id="task-id-1", content="Soda", is_completed=True)
    ]

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "task-id-1", "rename": "Milk"},
        target={"entity_id": "todo.name"},
        blocking=True,
    )
    assert api.update_task.called
    args = api.update_task.call_args
    assert args
    assert args.kwargs.get("task_id") == "task-id-1"
    assert args.kwargs.get("content") == "Milk"


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
    # Fake API response when state is refreshed after close
    api.get_tasks.return_value = []

    await hass.services.async_call(
        TODO_DOMAIN,
        "remove_item",
        {"item": ["task-id-1", "task-id-2"]},
        target={"entity_id": "todo.name"},
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
