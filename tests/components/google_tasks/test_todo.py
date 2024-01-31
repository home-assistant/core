"""Tests for Google Tasks todo platform."""


from collections.abc import Awaitable, Callable
from http import HTTPStatus
import json
from typing import Any
from unittest.mock import Mock, patch

from httplib2 import Response
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.typing import WebSocketGenerator

ENTITY_ID = "todo.my_tasks"
ITEM = {
    "id": "task-list-id-1",
    "title": "My tasks",
}
LIST_TASK_LIST_RESPONSE = {
    "items": [ITEM],
}
EMPTY_RESPONSE = {}
LIST_TASKS_RESPONSE = {
    "items": [],
}
ERROR_RESPONSE = {
    "error": {
        "code": 400,
        "message": "Invalid task ID",
        "errors": [
            {"message": "Invalid task ID", "domain": "global", "reason": "invalid"}
        ],
    }
}
CONTENT_ID = "Content-ID"
BOUNDARY = "batch_00972cc8-75bd-11ee-9692-0242ac110002"  # Arbitrary uuid

LIST_TASKS_RESPONSE_WATER = {
    "items": [
        {
            "id": "some-task-id",
            "title": "Water",
            "status": "needsAction",
            "description": "Any size is ok",
            "position": "00000000000000000001",
        },
    ],
}
LIST_TASKS_RESPONSE_MULTIPLE = {
    "items": [
        {
            "id": "some-task-id-2",
            "title": "Milk",
            "status": "needsAction",
            "position": "00000000000000000002",
        },
        {
            "id": "some-task-id-1",
            "title": "Water",
            "status": "needsAction",
            "position": "00000000000000000001",
        },
        {
            "id": "some-task-id-3",
            "title": "Cheese",
            "status": "needsAction",
            "position": "00000000000000000003",
        },
    ],
}
LIST_TASKS_RESPONSE_REORDER = {
    "items": [
        {
            "id": "some-task-id-2",
            "title": "Milk",
            "status": "needsAction",
            "position": "00000000000000000002",
        },
        {
            "id": "some-task-id-1",
            "title": "Water",
            "status": "needsAction",
            "position": "00000000000000000001",
        },
        # Task 3 moved after task 1
        {
            "id": "some-task-id-3",
            "title": "Cheese",
            "status": "needsAction",
            "position": "000000000000000000011",
        },
    ],
}

# API responses when testing update methods
UPDATE_API_RESPONSES = [
    LIST_TASK_LIST_RESPONSE,
    LIST_TASKS_RESPONSE_WATER,
    EMPTY_RESPONSE,  # update
    LIST_TASKS_RESPONSE,  # refresh after update
]
CREATE_API_RESPONSES = [
    LIST_TASK_LIST_RESPONSE,
    LIST_TASKS_RESPONSE,
    EMPTY_RESPONSE,  # create
    LIST_TASKS_RESPONSE,  # refresh
]


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.TODO]


@pytest.fixture
async def ws_get_items(
    hass_ws_client: WebSocketGenerator,
) -> Callable[[], Awaitable[dict[str, str]]]:
    """Fixture to fetch items from the todo websocket."""

    async def get() -> list[dict[str, str]]:
        # Fetch items using To-do platform
        client = await hass_ws_client()
        await client.send_json_auto_id(
            {
                "type": "todo/item/list",
                "entity_id": ENTITY_ID,
            }
        )
        resp = await client.receive_json()
        assert resp.get("success")
        return resp.get("result", {}).get("items", [])

    return get


@pytest.fixture(name="api_responses")
def mock_api_responses() -> list[dict | list]:
    """Fixture for API responses to return during test."""
    return []


def create_response_object(api_response: dict | list) -> tuple[Response, bytes]:
    """Create an http response."""
    return (
        Response({"Content-Type": "application/json"}),
        json.dumps(api_response).encode(),
    )


def create_batch_response_object(
    content_ids: list[str], api_responses: list[dict | list | Response]
) -> tuple[Response, bytes]:
    """Create a batch response in the multipart/mixed format."""
    assert len(api_responses) == len(content_ids)
    content = []
    for api_response in api_responses:
        status = 200
        body = ""
        if isinstance(api_response, Response):
            status = api_response.status
        else:
            body = json.dumps(api_response)
        content.extend(
            [
                f"--{BOUNDARY}",
                "Content-Type: application/http",
                f"{CONTENT_ID}: {content_ids.pop()}",
                "",
                f"HTTP/1.1 {status} OK",
                "Content-Type: application/json; charset=UTF-8",
                "",
                body,
            ]
        )
    content.append(f"--{BOUNDARY}--")
    body = ("\r\n".join(content)).encode()
    return (
        Response(
            {
                "Content-Type": f"multipart/mixed; boundary={BOUNDARY}",
                "Content-ID": "1",
            }
        ),
        body,
    )


def create_batch_response_handler(
    api_responses: list[dict | list | Response],
) -> Callable[[Any], tuple[Response, bytes]]:
    """Create a fake http2lib response handler that supports generating batch responses.

    Multi-part response objects are dynamically generated since they
    need to match the Content-ID of the incoming request.
    """

    def _handler(url, method, **kwargs) -> tuple[Response, bytes]:
        next_api_response = api_responses.pop(0)
        if method == "POST" and (body := kwargs.get("body")):
            content_ids = [
                line[len(CONTENT_ID) + 2 :]
                for line in body.splitlines()
                if line.startswith(f"{CONTENT_ID}:")
            ]
            if content_ids:
                return create_batch_response_object(content_ids, next_api_response)
        return create_response_object(next_api_response)

    return _handler


@pytest.fixture(name="response_handler")
def mock_response_handler(api_responses: list[dict | list]) -> list:
    """Create a mock http2lib response handler."""
    return [create_response_object(api_response) for api_response in api_responses]


@pytest.fixture(autouse=True)
def mock_http_response(response_handler: list | Callable) -> Mock:
    """Fixture to fake out http2lib responses."""

    with patch("httplib2.Http.request", side_effect=response_handler) as mock_response:
        yield mock_response


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            {
                "items": [
                    {
                        "id": "task-1",
                        "title": "Task 1",
                        "status": "needsAction",
                        "position": "0000000000000001",
                        "due": "2023-11-18T00:00:00+00:00",
                    },
                    {
                        "id": "task-2",
                        "title": "Task 2",
                        "status": "completed",
                        "position": "0000000000000002",
                        "notes": "long description",
                    },
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
            "due": "2023-11-18",
        },
        {
            "uid": "task-2",
            "summary": "Task 2",
            "status": "completed",
            "description": "long description",
        },
    ]

    # State reflect that one task needs action
    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    "response_handler",
    [
        ([(Response({"status": HTTPStatus.INTERNAL_SERVER_ERROR}), b"")]),
    ],
)
async def test_list_items_server_error(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    hass_ws_client: WebSocketGenerator,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test an error returned by the server when setting up the platform."""

    assert await integration_setup()

    await hass_ws_client(hass)

    state = hass.states.get("todo.my_tasks")
    assert state is None


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
            ERROR_RESPONSE,
        ]
    ],
)
async def test_task_items_error_response(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    hass_ws_client: WebSocketGenerator,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test an error while getting todo list items."""

    assert await integration_setup()

    await hass_ws_client(hass)

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "unavailable"


@pytest.mark.parametrize(
    ("api_responses", "item_data"),
    [
        (CREATE_API_RESPONSES, {}),
        (CREATE_API_RESPONSES, {"due_date": "2023-11-18"}),
        (CREATE_API_RESPONSES, {"description": "6-pack"}),
    ],
    ids=["summary", "due", "description"],
)
async def test_create_todo_list_item(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Mock,
    item_data: dict[str, Any],
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
        {"item": "Soda", **item_data},
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
            ERROR_RESPONSE,
        ]
    ],
)
async def test_create_todo_list_item_error(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for an error response when creating a To-do Item."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "1"

    with pytest.raises(HomeAssistantError, match="Invalid task ID"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "add_item",
            {"item": "Soda"},
            target={"entity_id": "todo.my_tasks"},
            blocking=True,
        )


@pytest.mark.parametrize("api_responses", [UPDATE_API_RESPONSES])
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
            ERROR_RESPONSE,  # update fails
        ]
    ],
)
async def test_update_todo_list_item_error(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for an error response when updating a To-do Item."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "1"

    with pytest.raises(HomeAssistantError, match="Invalid task ID"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "update_item",
            {"item": "some-task-id", "rename": "Soda", "status": "completed"},
            target={"entity_id": "todo.my_tasks"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("api_responses", "item_data"),
    [
        (UPDATE_API_RESPONSES, {"rename": "Soda"}),
        (UPDATE_API_RESPONSES, {"due_date": "2023-11-18"}),
        (UPDATE_API_RESPONSES, {"due_date": None}),
        (UPDATE_API_RESPONSES, {"description": "At least one gallon"}),
        (UPDATE_API_RESPONSES, {"description": ""}),
        (UPDATE_API_RESPONSES, {"description": None}),
    ],
    ids=(
        "rename",
        "due_date",
        "clear_due_date",
        "description",
        "empty_description",
        "clear_description",
    ),
)
async def test_partial_update(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    item_data: dict[str, Any],
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
        {"item": "some-task-id", **item_data},
        target={"entity_id": "todo.my_tasks"},
        blocking=True,
    )
    assert len(mock_http_response.call_args_list) == 4
    call = mock_http_response.call_args_list[2]
    assert call
    assert call.args == snapshot
    assert call.kwargs.get("body") == snapshot


@pytest.mark.parametrize("api_responses", [UPDATE_API_RESPONSES])
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


@pytest.mark.parametrize(
    "response_handler",
    [
        (
            create_batch_response_handler(
                [
                    LIST_TASK_LIST_RESPONSE,
                    LIST_TASKS_RESPONSE_MULTIPLE,
                    [EMPTY_RESPONSE, EMPTY_RESPONSE, EMPTY_RESPONSE],  # Delete batch
                    LIST_TASKS_RESPONSE,  # refresh after delete
                ]
            )
        )
    ],
)
async def test_delete_todo_list_item(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for deleting multiple To-do Items."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "3"

    await hass.services.async_call(
        TODO_DOMAIN,
        "remove_item",
        {"item": ["some-task-id-1", "some-task-id-2", "some-task-id-3"]},
        target={"entity_id": "todo.my_tasks"},
        blocking=True,
    )
    assert len(mock_http_response.call_args_list) == 4
    call = mock_http_response.call_args_list[2]
    assert call
    assert call.args == snapshot


@pytest.mark.parametrize(
    "response_handler",
    [
        (
            create_batch_response_handler(
                [
                    LIST_TASK_LIST_RESPONSE,
                    LIST_TASKS_RESPONSE_MULTIPLE,
                    [
                        EMPTY_RESPONSE,
                        ERROR_RESPONSE,  # one item is a failure
                        EMPTY_RESPONSE,
                    ],
                    LIST_TASKS_RESPONSE,  # refresh after create
                ]
            )
        )
    ],
)
async def test_delete_partial_failure(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for partial failure when deleting multiple To-do Items."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "3"

    with pytest.raises(HomeAssistantError, match="Invalid task ID"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "remove_item",
            {"item": ["some-task-id-1", "some-task-id-2", "some-task-id-3"]},
            target={"entity_id": "todo.my_tasks"},
            blocking=True,
        )


@pytest.mark.parametrize(
    "response_handler",
    [
        (
            create_batch_response_handler(
                [
                    LIST_TASK_LIST_RESPONSE,
                    LIST_TASKS_RESPONSE_MULTIPLE,
                    [
                        "1234-invalid-json",
                    ],
                ]
            )
        )
    ],
)
async def test_delete_invalid_json_response(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test delete with an invalid json response."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "3"

    with pytest.raises(HomeAssistantError, match="unexpected response"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "remove_item",
            {"item": ["some-task-id-1"]},
            target={"entity_id": "todo.my_tasks"},
            blocking=True,
        )


@pytest.mark.parametrize(
    "response_handler",
    [
        (
            create_batch_response_handler(
                [
                    LIST_TASK_LIST_RESPONSE,
                    LIST_TASKS_RESPONSE_MULTIPLE,
                    [Response({"status": HTTPStatus.INTERNAL_SERVER_ERROR})],
                ]
            )
        )
    ],
)
async def test_delete_server_error(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test delete with an invalid json response."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "3"

    with pytest.raises(HomeAssistantError, match="responded with error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "remove_item",
            {"item": ["some-task-id-1"]},
            target={"entity_id": "todo.my_tasks"},
            blocking=True,
        )


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            {
                "items": [
                    {
                        "id": "task-3-2",
                        "title": "Child 2",
                        "status": "needsAction",
                        "parent": "task-3",
                        "position": "0000000000000002",
                    },
                    {
                        "id": "task-3",
                        "title": "Task 3 (Parent)",
                        "status": "needsAction",
                        "position": "0000000000000003",
                    },
                    {
                        "id": "task-2",
                        "title": "Task 2",
                        "status": "needsAction",
                        "position": "0000000000000002",
                    },
                    {
                        "id": "task-1",
                        "title": "Task 1",
                        "status": "needsAction",
                        "position": "0000000000000001",
                    },
                    {
                        "id": "task-3-1",
                        "title": "Child 1",
                        "status": "needsAction",
                        "parent": "task-3",
                        "position": "0000000000000001",
                    },
                    {
                        "id": "task-4",
                        "title": "Task 4",
                        "status": "needsAction",
                        "position": "0000000000000004",
                    },
                ],
            },
        ]
    ],
)
async def test_parent_child_ordering(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting todo list items."""

    assert await integration_setup()

    state = hass.states.get("todo.my_tasks")
    assert state
    assert state.state == "4"

    items = await ws_get_items()
    assert items == snapshot


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            LIST_TASKS_RESPONSE_MULTIPLE,
            EMPTY_RESPONSE,  # move
            LIST_TASKS_RESPONSE_REORDER,  # refresh after move
        ]
    ],
)
async def test_move_todo_item(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    hass_ws_client: WebSocketGenerator,
    mock_http_response: Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for re-ordering a To-do Item."""

    assert await integration_setup()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "3"

    items = await ws_get_items()
    assert items == snapshot

    # Move to second in the list
    client = await hass_ws_client()
    data = {
        "id": id,
        "type": "todo/item/move",
        "entity_id": ENTITY_ID,
        "uid": "some-task-id-3",
        "previous_uid": "some-task-id-1",
    }
    await client.send_json_auto_id(data)
    resp = await client.receive_json()
    assert resp.get("success")

    assert len(mock_http_response.call_args_list) == 4
    call = mock_http_response.call_args_list[2]
    assert call
    assert call.args == snapshot
    assert call.kwargs.get("body") == snapshot

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "3"

    items = await ws_get_items()
    assert items == snapshot


@pytest.mark.parametrize(
    "api_responses",
    [
        [
            LIST_TASK_LIST_RESPONSE,
            LIST_TASKS_RESPONSE_WATER,
            EMPTY_RESPONSE,  # update
            # refresh after update
            {
                "items": [
                    {
                        "id": "some-task-id",
                        "title": "Milk",
                        "status": "needsAction",
                        "position": "0000000000000001",
                    },
                ],
            },
        ]
    ],
)
async def test_susbcribe(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribing to item updates."""

    assert await integration_setup()

    # Subscribe and get the initial list
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/subscribe",
            "entity_id": "todo.my_tasks",
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
    assert items[0]["summary"] == "Water"
    assert items[0]["status"] == "needs_action"
    uid = items[0]["uid"]
    assert uid

    # Rename item
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": uid, "rename": "Milk"},
        target={"entity_id": "todo.my_tasks"},
        blocking=True,
    )

    # Verify update is published
    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    items = msg["event"].get("items")
    assert items
    assert len(items) == 1
    assert items[0]["summary"] == "Milk"
    assert items[0]["status"] == "needs_action"
    assert "uid" in items[0]
