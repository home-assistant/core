"""Tests for Google Tasks todo platform."""


from collections.abc import Awaitable, Callable
import json
from typing import Any
from unittest.mock import Mock, patch

from httplib2 import Response
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.typing import WebSocketGenerator

ENTITY_ID = "todo.my_tasks"
LIST_TASK_LIST_RESPONSE = {
    "items": [
        {
            "id": "task-list-id-1",
            "title": "My tasks",
        },
    ]
}
EMPTY_RESPONSE = {}
LIST_TASKS_RESPONSE = {
    "items": [],
}

LIST_TASKS_RESPONSE_WATER = {
    "items": [
        {"id": "some-task-id", "title": "Water", "status": "needsAction"},
    ],
}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.TODO]


@pytest.fixture
def ws_req_id() -> Callable[[], int]:
    """Fixture for incremental websocket requests."""

    id = 0

    def next_id() -> int:
        nonlocal id
        id += 1
        return id

    return next_id


@pytest.fixture
async def ws_get_items(
    hass_ws_client: WebSocketGenerator, ws_req_id: Callable[[], int]
) -> Callable[[], Awaitable[dict[str, str]]]:
    """Fixture to fetch items from the todo websocket."""

    async def get() -> list[dict[str, str]]:
        # Fetch items using To-do platform
        client = await hass_ws_client()
        id = ws_req_id()
        await client.send_json(
            {
                "id": id,
                "type": "todo/item/list",
                "entity_id": ENTITY_ID,
            }
        )
        resp = await client.receive_json()
        assert resp.get("id") == id
        assert resp.get("success")
        return resp.get("result", {}).get("items", [])

    return get


@pytest.fixture(name="api_responses")
def mock_api_responses() -> list[dict | list]:
    """Fixture for API responses to return during test."""
    return []


@pytest.fixture(autouse=True)
def mock_http_response(api_responses: list[dict | list]) -> Mock:
    """Fixture to fake out http2lib responses."""
    responses = [
        (Response({}), bytes(json.dumps(api_response), encoding="utf-8"))
        for api_response in api_responses
    ]
    with patch("httplib2.Http.request", side_effect=responses) as mock_response:
        yield mock_response


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            {
                "items": [
                    {"id": "task-1", "title": "Task 1", "status": "needsAction"},
                    {"id": "task-2", "title": "Task 2", "status": "completed"},
                ],
            },
        ]
    ],
)
async def test_get_items(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    hass_ws_client: WebSocketGenerator,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test getting todo list items."""

    assert await integration_setup()

    await hass_ws_client(hass)

    items = await ws_get_items()
    assert items == [
        {
            "uid": "task-1",
            "summary": "Task 1",
            "status": "needs_action",
        },
        {
            "uid": "task-2",
            "summary": "Task 2",
            "status": "completed",
        },
    ]

    # State reflect that one task needs action
    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            LIST_TASKS_RESPONSE,
        ]
    ],
)
async def test_empty_todo_list(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    hass_ws_client: WebSocketGenerator,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test getting todo list items."""

    assert await integration_setup()

    await hass_ws_client(hass)

    items = await ws_get_items()
    assert items == []

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "0"


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            LIST_TASKS_RESPONSE,
            EMPTY_RESPONSE,  # create
            LIST_TASKS_RESPONSE,  # refresh after create
        ]
    ],
)
async def test_create_todo_list_item(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for creating a To-do Item."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "0"

    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "Soda"},
        target={"entity_id": "todo.my_tasks"},
        blocking=True,
    )
    assert len(mock_http_response.call_args_list) == 4
    call = mock_http_response.call_args_list[2]
    assert call
    assert call.args == snapshot
    assert call.kwargs.get("body") == snapshot


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            LIST_TASKS_RESPONSE_WATER,
            EMPTY_RESPONSE,  # update
            LIST_TASKS_RESPONSE,  # refresh after update
        ]
    ],
)
async def test_update_todo_list_item(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for updating a To-do Item."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "1"

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "some-task-id", "rename": "Soda", "status": "completed"},
        target={"entity_id": "todo.my_tasks"},
        blocking=True,
    )
    assert len(mock_http_response.call_args_list) == 4
    call = mock_http_response.call_args_list[2]
    assert call
    assert call.args == snapshot
    assert call.kwargs.get("body") == snapshot


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            LIST_TASKS_RESPONSE_WATER,
            EMPTY_RESPONSE,  # update
            LIST_TASKS_RESPONSE,  # refresh after update
        ]
    ],
)
async def test_partial_update_title(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for partial update with title only."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "1"

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "some-task-id", "rename": "Soda"},
        target={"entity_id": "todo.my_tasks"},
        blocking=True,
    )
    assert len(mock_http_response.call_args_list) == 4
    call = mock_http_response.call_args_list[2]
    assert call
    assert call.args == snapshot
    assert call.kwargs.get("body") == snapshot


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            LIST_TASKS_RESPONSE_WATER,
            EMPTY_RESPONSE,  # update
            LIST_TASKS_RESPONSE,  # refresh after update
        ]
    ],
)
async def test_partial_update_status(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for partial update with status only."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "1"

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "some-task-id", "status": "needs_action"},
        target={"entity_id": "todo.my_tasks"},
        blocking=True,
    )
    assert len(mock_http_response.call_args_list) == 4
    call = mock_http_response.call_args_list[2]
    assert call
    assert call.args == snapshot
    assert call.kwargs.get("body") == snapshot
