"""Test shopping list todo platform."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.typing import WebSocketGenerator

TEST_ENTITY = "todo.shopping_list"


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
                "entity_id": TEST_ENTITY,
            }
        )
        resp = await client.receive_json()
        assert resp.get("success")
        return resp.get("result", {}).get("items", [])

    return get


@pytest.fixture
async def ws_move_item(
    hass_ws_client: WebSocketGenerator,
) -> Callable[[str, str | None], Awaitable[None]]:
    """Fixture to move an item in the todo list."""

    async def move(uid: str, previous_uid: str | None) -> dict[str, Any]:
        # Fetch items using To-do platform
        client = await hass_ws_client()
        data = {
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": uid,
        }
        if previous_uid is not None:
            data["previous_uid"] = previous_uid
        await client.send_json_auto_id(data)
        resp = await client.receive_json()
        return resp

    return move


async def test_get_items(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test creating a shopping list item with the WS API and verifying with To-do API."""
    client = await hass_ws_client(hass)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    # Native shopping list websocket
    await client.send_json_auto_id({"type": "shopping_list/items/add", "name": "soda"})
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert data["name"] == "soda"
    assert data["complete"] is False

    # Fetch items using To-do platform
    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["summary"] == "soda"
    assert items[0]["status"] == "needs_action"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


async def test_add_item(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test adding shopping_list item and listing it."""
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {
            "item": "soda",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Fetch items using To-do platform
    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["summary"] == "soda"
    assert items[0]["status"] == "needs_action"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


async def test_remove_item(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test removing a todo item."""
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "soda"},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )
    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["summary"] == "soda"
    assert items[0]["status"] == "needs_action"
    assert "uid" in items[0]

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    await hass.services.async_call(
        TODO_DOMAIN,
        "remove_item",
        {
            "item": [items[0]["uid"]],
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 0

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"


async def test_bulk_remove(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test removing a todo item."""

    for _i in range(0, 5):
        await hass.services.async_call(
            TODO_DOMAIN,
            "add_item",
            {
                "item": "soda",
            },
            target={"entity_id": TEST_ENTITY},
            blocking=True,
        )

    items = await ws_get_items()
    assert len(items) == 5
    uids = [item["uid"] for item in items]

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "5"

    await hass.services.async_call(
        TODO_DOMAIN,
        "remove_item",
        {
            "item": uids,
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 0

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"


async def test_update_item(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test updating a todo item."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {
            "item": "soda",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Fetch item
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert item["status"] == "needs_action"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    # Mark item completed
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {
            "item": "soda",
            "status": "completed",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Verify item is marked as completed
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert item["status"] == "completed"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"


async def test_partial_update_item(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test updating a todo item with partial information."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {
            "item": "soda",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Fetch item
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert item["status"] == "needs_action"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    # Mark item completed without changing the summary
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {
            "item": item["uid"],
            "status": "completed",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Verify item is marked as completed
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert item["status"] == "completed"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    # Change the summary without changing the status
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {
            "item": item["uid"],
            "rename": "other summary",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Verify item is changed and still marked as completed
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "other summary"
    assert item["status"] == "completed"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"


async def test_update_invalid_item(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test updating a todo item that does not exist."""

    with pytest.raises(ServiceValidationError, match="Unable to find"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "update_item",
            {
                "item": "invalid-uid",
                "rename": "Example task",
            },
            target={"entity_id": TEST_ENTITY},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("src_idx", "dst_idx", "expected_items"),
    [
        # Move any item to the front of the list
        (0, None, ["item 1", "item 2", "item 3", "item 4"]),
        (1, None, ["item 2", "item 1", "item 3", "item 4"]),
        (2, None, ["item 3", "item 1", "item 2", "item 4"]),
        (3, None, ["item 4", "item 1", "item 2", "item 3"]),
        # Move items right
        (0, 1, ["item 2", "item 1", "item 3", "item 4"]),
        (0, 2, ["item 2", "item 3", "item 1", "item 4"]),
        (0, 3, ["item 2", "item 3", "item 4", "item 1"]),
        (1, 2, ["item 1", "item 3", "item 2", "item 4"]),
        (1, 3, ["item 1", "item 3", "item 4", "item 2"]),
        # Move items left
        (2, 0, ["item 1", "item 3", "item 2", "item 4"]),
        (3, 0, ["item 1", "item 4", "item 2", "item 3"]),
        (3, 1, ["item 1", "item 2", "item 4", "item 3"]),
        # No-ops
        (0, 0, ["item 1", "item 2", "item 3", "item 4"]),
        (2, 1, ["item 1", "item 2", "item 3", "item 4"]),
        (2, 2, ["item 1", "item 2", "item 3", "item 4"]),
        (3, 2, ["item 1", "item 2", "item 3", "item 4"]),
        (3, 3, ["item 1", "item 2", "item 3", "item 4"]),
    ],
)
async def test_move_item(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    ws_move_item: Callable[[str, str | None], Awaitable[dict[str, Any]]],
    src_idx: int,
    dst_idx: int | None,
    expected_items: list[str],
) -> None:
    """Test moving a todo item within the list."""

    for i in range(1, 5):
        await hass.services.async_call(
            TODO_DOMAIN,
            "add_item",
            {
                "item": f"item {i}",
            },
            target={"entity_id": TEST_ENTITY},
            blocking=True,
        )

    items = await ws_get_items()
    assert len(items) == 4
    uids = [item["uid"] for item in items]
    summaries = [item["summary"] for item in items]
    assert summaries == ["item 1", "item 2", "item 3", "item 4"]

    # Prepare items for moving
    previous_uid: str | None = None
    if dst_idx is not None:
        previous_uid = uids[dst_idx]

    resp = await ws_move_item(uids[src_idx], previous_uid)
    assert resp.get("success")

    items = await ws_get_items()
    assert len(items) == 4
    summaries = [item["summary"] for item in items]
    assert summaries == expected_items


async def test_move_invalid_item(
    hass: HomeAssistant,
    sl_setup: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    ws_move_item: Callable[[str, int | None], Awaitable[dict[str, Any]]],
) -> None:
    """Test moving an item that does not exist."""

    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "soda"},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"

    resp = await ws_move_item("unknown", 0)
    assert not resp.get("success")
    assert resp.get("error", {}).get("code") == "failed"
    assert "could not be re-ordered" in resp.get("error", {}).get("message")


async def test_subscribe_item(
    hass: HomeAssistant,
    sl_setup: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test updating a todo item."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {
            "item": "soda",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Subscribe and get the initial list
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/subscribe",
            "entity_id": TEST_ENTITY,
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
    assert items[0]["summary"] == "soda"
    assert items[0]["status"] == "needs_action"
    uid = items[0]["uid"]
    assert uid

    # Rename item item completed
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {
            "item": "soda",
            "rename": "milk",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    # Verify update is published
    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    items = msg["event"].get("items")
    assert items
    assert len(items) == 1
    assert items[0]["summary"] == "milk"
    assert items[0]["status"] == "needs_action"
    assert "uid" in items[0]
