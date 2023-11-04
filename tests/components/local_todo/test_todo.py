"""Tests for todo platform of local_todo."""

from collections.abc import Awaitable, Callable
import textwrap

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

    async def move(uid: str, previous_uid: str | None) -> None:
        # Fetch items using To-do platform
        client = await hass_ws_client()
        id = ws_req_id()
        data = {
            "id": id,
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": uid,
        }
        if previous_uid is not None:
            data["previous_uid"] = previous_uid
        await client.send_json(data)
        resp = await client.receive_json()
        assert resp.get("id") == id
        assert resp.get("success")

    return move


async def test_add_item(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test adding a todo item."""

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "replace batteries"},
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


async def test_remove_item(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test removing a todo item."""
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "replace batteries"},
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
        "remove_item",
        {"item": [items[0]["uid"]]},
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
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test removing multiple todo items."""
    for i in range(0, 5):
        await hass.services.async_call(
            TODO_DOMAIN,
            "add_item",
            {"item": f"soda #{i}"},
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
        {"item": uids},
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
        "add_item",
        {"item": "soda"},
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
        {"item": item["uid"], "status": "completed"},
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
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    ws_move_item: Callable[[str, str | None], Awaitable[None]],
    src_idx: int,
    dst_idx: int | None,
    expected_items: list[str],
) -> None:
    """Test moving a todo item within the list."""
    for i in range(1, 5):
        await hass.services.async_call(
            TODO_DOMAIN,
            "add_item",
            {"item": f"item {i}"},
            target={"entity_id": TEST_ENTITY},
            blocking=True,
        )

    items = await ws_get_items()
    assert len(items) == 4
    uids = [item["uid"] for item in items]
    summaries = [item["summary"] for item in items]
    assert summaries == ["item 1", "item 2", "item 3", "item 4"]

    # Prepare items for moving
    previous_uid = None
    if dst_idx is not None:
        previous_uid = uids[dst_idx]
    await ws_move_item(uids[src_idx], previous_uid)

    items = await ws_get_items()
    assert len(items) == 4
    summaries = [item["summary"] for item in items]
    assert summaries == expected_items


async def test_move_item_unknown(
    hass: HomeAssistant,
    setup_integration: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test moving a todo item that does not exist."""

    # Prepare items for moving
    client = await hass_ws_client()
    data = {
        "id": 1,
        "type": "todo/item/move",
        "entity_id": TEST_ENTITY,
        "uid": "unknown",
        "previous_uid": "item-2",
    }
    await client.send_json(data)
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert not resp.get("success")
    assert resp.get("error", {}).get("code") == "failed"
    assert "not found in todo list" in resp["error"]["message"]


async def test_move_item_previous_unknown(
    hass: HomeAssistant,
    setup_integration: None,
    hass_ws_client: WebSocketGenerator,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test moving a todo item that does not exist."""

    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "item 1"},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )
    items = await ws_get_items()
    assert len(items) == 1

    # Prepare items for moving
    client = await hass_ws_client()
    data = {
        "id": 1,
        "type": "todo/item/move",
        "entity_id": TEST_ENTITY,
        "uid": items[0]["uid"],
        "previous_uid": "unknown",
    }
    await client.send_json(data)
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert not resp.get("success")
    assert resp.get("error", {}).get("code") == "failed"
    assert "not found in todo list" in resp["error"]["message"]


@pytest.mark.parametrize(
    ("ics_content", "expected_state"),
    [
        ("", "0"),
        (None, "0"),
        (
            textwrap.dedent(
                """\
                    BEGIN:VCALENDAR
                    PRODID:-//homeassistant.io//local_todo 1.0//EN
                    VERSION:2.0
                    BEGIN:VTODO
                    DTSTAMP:20231024T014011
                    UID:077cb7f2-6c89-11ee-b2a9-0242ac110002
                    CREATED:20231017T010348
                    LAST-MODIFIED:20231024T014011
                    SEQUENCE:1
                    STATUS:COMPLETED
                    SUMMARY:Complete Task
                    END:VTODO
                    END:VCALENDAR
                """
            ),
            "0",
        ),
        (
            textwrap.dedent(
                """\
                    BEGIN:VCALENDAR
                    PRODID:-//homeassistant.io//local_todo 1.0//EN
                    VERSION:2.0
                    BEGIN:VTODO
                    DTSTAMP:20231024T014011
                    UID:077cb7f2-6c89-11ee-b2a9-0242ac110002
                    CREATED:20231017T010348
                    LAST-MODIFIED:20231024T014011
                    SEQUENCE:1
                    STATUS:NEEDS-ACTION
                    SUMMARY:Incomplete Task
                    END:VTODO
                    END:VCALENDAR
                """
            ),
            "1",
        ),
    ],
    ids=("empty", "not_exists", "completed", "needs_action"),
)
async def test_parse_existing_ics(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_integration: None,
    expected_state: str,
) -> None:
    """Test parsing ics content."""

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state
