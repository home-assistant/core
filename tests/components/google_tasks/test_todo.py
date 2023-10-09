"""Tests for Google Tasks todo platform."""


from collections.abc import Awaitable, Callable
import json
from unittest.mock import patch

from httplib2 import Response
import pytest

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


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.TODO]


@pytest.fixture
def ws_req_id() -> Callable[[], int]:
    """Fixture for incremental websocket requests."""

    id = 0

    def next() -> int:
        nonlocal id
        id += 1
        return id

    return next


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
def mock_http_response(api_responses: list[dict | list]) -> None:
    """Fixture to fake out http2lib responses."""
    responses = [
        (Response({}), bytes(json.dumps(api_response), encoding="utf-8"))
        for api_response in api_responses
    ]
    with patch("httplib2.Http.request", side_effect=responses):
        yield


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
            "status": "NEEDS-ACTION",
        },
        {
            "uid": "task-2",
            "summary": "Task 2",
            "status": "COMPLETED",
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
            {
                "items": [],
            },
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
