"""Tests for todo platform of local_todo."""

from collections.abc import Awaitable, Callable

import pytest

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY

from tests.typing import WebSocketGenerator


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
                "entity_id": TEST_ENTITY,
            }
        )
        resp = await client.receive_json()
        assert resp.get("id") == id
        assert resp.get("success")
        return resp.get("result", {}).get("items", [])

    return get


@pytest.fixture
async def ws_move_item(
    hass_ws_client: WebSocketGenerator,
    ws_req_id: Callable[[], int],
) -> Callable[[str, str | None], Awaitable[None]]:
    """Fixture to move an item in the todo list."""

    async def move(uid: str, pos: int) -> None:
        # Fetch items using To-do platform
        client = await hass_ws_client()
        id = ws_req_id()
        data = {
            "id": id,
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "pos": pos,
        }
        await client.send_json(data)
        resp = await client.receive_json()
        assert resp.get("id") == id
        assert resp.get("success")

    return move


async def test_create_item(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test creating a todo item."""

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    await hass.services.async_call(
        TODO_DOMAIN,
        "create_item",
        {"summary": "replace batteries"},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["summary"] == "replace batteries"
    assert items[0]["status"] == "needs_action"
    assert "uid" in items[0]

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


async def test_delete_item(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test deleting a todo item."""
    await hass.services.async_call(
        TODO_DOMAIN,
        "create_item",
        {"summary": "replace batteries"},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["summary"] == "replace batteries"
    assert items[0]["status"] == "needs_action"
    assert "uid" in items[0]

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    await hass.services.async_call(
        TODO_DOMAIN,
        "delete_item",
        {"uid": [items[0]["uid"]]},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 0

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"


async def test_bulk_delete(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test deleting a todo item."""
    for i in range(0, 5):
        await hass.services.async_call(
            TODO_DOMAIN,
            "create_item",
            {"summary": f"soda #{i}"},
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
        "delete_item",
        {"uid": uids},
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
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test updating a todo item."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        "create_item",
        {"summary": "soda"},
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
        {"uid": item["uid"], "status": "completed"},
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


@pytest.mark.parametrize(
    ("src_idx", "pos", "expected_items"),
    [
        # Move any item to the front of the list
        (0, 0, ["item 1", "item 2", "item 3", "item 4"]),
        (1, 0, ["item 2", "item 1", "item 3", "item 4"]),
        (2, 0, ["item 3", "item 1", "item 2", "item 4"]),
        (3, 0, ["item 4", "item 1", "item 2", "item 3"]),
        # Move items right
        (0, 1, ["item 2", "item 1", "item 3", "item 4"]),
        (0, 2, ["item 2", "item 3", "item 1", "item 4"]),
        (0, 3, ["item 2", "item 3", "item 4", "item 1"]),
        (1, 2, ["item 1", "item 3", "item 2", "item 4"]),
        (1, 3, ["item 1", "item 3", "item 4", "item 2"]),
        (1, 4, ["item 1", "item 3", "item 4", "item 2"]),
        (1, 5, ["item 1", "item 3", "item 4", "item 2"]),
        # Move items left
        (2, 1, ["item 1", "item 3", "item 2", "item 4"]),
        (3, 1, ["item 1", "item 4", "item 2", "item 3"]),
        (3, 2, ["item 1", "item 2", "item 4", "item 3"]),
        # No-ops
        (1, 1, ["item 1", "item 2", "item 3", "item 4"]),
        (2, 2, ["item 1", "item 2", "item 3", "item 4"]),
        (3, 3, ["item 1", "item 2", "item 3", "item 4"]),
        (3, 4, ["item 1", "item 2", "item 3", "item 4"]),
    ],
)
async def test_move_item(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    ws_move_item: Callable[[str, str | None], Awaitable[None]],
    src_idx: int,
    pos: int,
    expected_items: list[str],
) -> None:
    """Test moving a todo item within the list."""
    for i in range(1, 5):
        await hass.services.async_call(
            TODO_DOMAIN,
            "create_item",
            {"summary": f"item {i}"},
            target={"entity_id": TEST_ENTITY},
            blocking=True,
        )

    items = await ws_get_items()
    assert len(items) == 4
    uids = [item["uid"] for item in items]
    summaries = [item["summary"] for item in items]
    assert summaries == ["item 1", "item 2", "item 3", "item 4"]

    # Prepare items for moving
    await ws_move_item(uids[src_idx], pos)

    items = await ws_get_items()
    assert len(items) == 4
    summaries = [item["summary"] for item in items]
    assert summaries == expected_items
