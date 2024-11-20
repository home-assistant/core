"""Tests for todo platform of local_todo."""

from collections.abc import Awaitable, Callable
import textwrap
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

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
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY

from tests.typing import WebSocketGenerator


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

    async def move(uid: str, previous_uid: str | None) -> None:
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
        assert resp.get("success")

    return move


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant) -> None:
    """Set the time zone for the tests that keesp UTC-6 all year round."""
    await hass.config.async_set_time_zone("America/Regina")


EXPECTED_ADD_ITEM = {
    "status": "needs_action",
    "summary": "replace batteries",
}


@pytest.mark.parametrize(
    ("item_data", "expected_item_data"),
    [
        ({}, EXPECTED_ADD_ITEM),
        ({ATTR_DUE_DATE: "2023-11-17"}, {**EXPECTED_ADD_ITEM, "due": "2023-11-17"}),
        (
            {ATTR_DUE_DATETIME: "2023-11-17T11:30:00+00:00"},
            {**EXPECTED_ADD_ITEM, "due": "2023-11-17T05:30:00-06:00"},
        ),
        (
            {ATTR_DESCRIPTION: "Additional detail"},
            {**EXPECTED_ADD_ITEM, "description": "Additional detail"},
        ),
        ({ATTR_DESCRIPTION: ""}, {**EXPECTED_ADD_ITEM, "description": ""}),
        ({ATTR_DESCRIPTION: None}, EXPECTED_ADD_ITEM),
    ],
)
async def test_add_item(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    item_data: dict[str, Any],
    expected_item_data: dict[str, Any],
) -> None:
    """Test adding a todo item."""

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "replace batteries", **item_data},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 1
    item_data = items[0]
    assert "uid" in item_data
    del item_data["uid"]
    assert item_data == expected_item_data

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    ("item_data", "expected_item_data"),
    [
        ({}, {}),
        ({ATTR_DUE_DATE: "2023-11-17"}, {"due": "2023-11-17"}),
        (
            {"due_datetime": "2023-11-17T11:30:00+00:00"},
            {"due": "2023-11-17T05:30:00-06:00"},
        ),
        ({ATTR_DESCRIPTION: "Additional detail"}, {"description": "Additional detail"}),
    ],
)
async def test_remove_item(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    item_data: dict[str, Any],
    expected_item_data: dict[str, Any],
) -> None:
    """Test removing a todo item."""
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "replace batteries", **item_data},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["summary"] == "replace batteries"
    assert items[0]["status"] == "needs_action"
    for k, v in expected_item_data.items():
        assert items[0][k] == v
    assert "uid" in items[0]

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: [items[0]["uid"]]},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
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
    for i in range(5):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: f"soda #{i}"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
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
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: uids},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 0

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"


EXPECTED_UPDATE_ITEM = {
    "status": "needs_action",
    "summary": "soda",
}


@pytest.mark.parametrize(
    ("item_data", "expected_item_data", "expected_state"),
    [
        (
            {ATTR_STATUS: "completed"},
            {**EXPECTED_UPDATE_ITEM, "status": "completed"},
            "0",
        ),
        (
            {ATTR_DUE_DATE: "2023-11-17"},
            {**EXPECTED_UPDATE_ITEM, "due": "2023-11-17"},
            "1",
        ),
        (
            {ATTR_DUE_DATETIME: "2023-11-17T11:30:00+00:00"},
            {**EXPECTED_UPDATE_ITEM, "due": "2023-11-17T05:30:00-06:00"},
            "1",
        ),
        (
            {ATTR_DESCRIPTION: "Additional detail"},
            {**EXPECTED_UPDATE_ITEM, "description": "Additional detail"},
            "1",
        ),
    ],
)
async def test_update_item(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    item_data: dict[str, Any],
    expected_item_data: dict[str, Any],
    expected_state: str,
) -> None:
    """Test updating a todo item."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "soda"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
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

    # Update item
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: item["uid"], **item_data},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    # Verify item is updated
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert "uid" in item
    del item["uid"]
    assert item == expected_item_data

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("item_data", "expected_item_data"),
    [
        (
            {ATTR_STATUS: "completed"},
            {
                "summary": "soda",
                "status": "completed",
                "description": "Additional detail",
                "due": "2024-01-01",
            },
        ),
        (
            {ATTR_DUE_DATE: "2024-01-02"},
            {
                "summary": "soda",
                "status": "needs_action",
                "description": "Additional detail",
                "due": "2024-01-02",
            },
        ),
        (
            {ATTR_DUE_DATE: None},
            {
                "summary": "soda",
                "status": "needs_action",
                "description": "Additional detail",
            },
        ),
        (
            {ATTR_DUE_DATETIME: "2024-01-01 10:30:00"},
            {
                "summary": "soda",
                "status": "needs_action",
                "description": "Additional detail",
                "due": "2024-01-01T10:30:00-06:00",
            },
        ),
        (
            {ATTR_DUE_DATETIME: None},
            {
                "summary": "soda",
                "status": "needs_action",
                "description": "Additional detail",
            },
        ),
        (
            {ATTR_DESCRIPTION: "updated description"},
            {
                "summary": "soda",
                "status": "needs_action",
                "due": "2024-01-01",
                "description": "updated description",
            },
        ),
        (
            {ATTR_DESCRIPTION: None},
            {"summary": "soda", "status": "needs_action", "due": "2024-01-01"},
        ),
    ],
    ids=[
        "status",
        "due_date",
        "clear_due_date",
        "due_datetime",
        "clear_due_datetime",
        "description",
        "clear_description",
    ],
)
async def test_update_existing_field(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    item_data: dict[str, Any],
    expected_item_data: dict[str, Any],
) -> None:
    """Test updating a todo item."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ITEM: "soda",
            ATTR_DESCRIPTION: "Additional detail",
            ATTR_DUE_DATE: "2024-01-01",
        },
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    # Fetch item
    items = await ws_get_items()
    assert len(items) == 1

    item = items[0]
    assert item["summary"] == "soda"
    assert item["status"] == "needs_action"

    # Perform update
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: item["uid"], **item_data},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    # Verify item is updated
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert "uid" in item
    del item["uid"]
    assert item == expected_item_data


async def test_rename(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
) -> None:
    """Test renaming a todo item."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "soda"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
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

    # Rename item
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: item["uid"], ATTR_RENAME: "water"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    # Verify item has been renamed
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "water"
    assert item["status"] == "needs_action"

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


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
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: f"item {i}"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
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
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "item 1"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
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
                    SUMMARY:Task
                    DUE:20231023
                    END:VTODO
                    END:VCALENDAR
                """
            ),
            "1",
        ),
        (
            textwrap.dedent(
                """\
                    BEGIN:VCALENDAR
                    PRODID:-//homeassistant.io//local_todo 2.0//EN
                    VERSION:2.0
                    BEGIN:VTODO
                    DTSTAMP:20231024T014011
                    UID:077cb7f2-6c89-11ee-b2a9-0242ac110002
                    CREATED:20231017T010348
                    LAST-MODIFIED:20231024T014011
                    SEQUENCE:1
                    STATUS:NEEDS-ACTION
                    SUMMARY:Task
                    DUE:20231024
                    END:VTODO
                    END:VCALENDAR
                """
            ),
            "1",
        ),
        (
            textwrap.dedent(
                """\
                    BEGIN:VCALENDAR
                    PRODID:-//homeassistant.io//local_todo 2.0//EN
                    VERSION:2.0
                    BEGIN:VTODO
                    DTSTAMP:20231024T014011
                    UID:077cb7f2-6c89-11ee-b2a9-0242ac110002
                    CREATED:20231017T010348
                    LAST-MODIFIED:20231024T014011
                    SEQUENCE:1
                    STATUS:NEEDS-ACTION
                    SUMMARY:Task
                    DUE:20231024T113000
                    DTSTART;TZID=CST:20231024T113000
                    END:VTODO
                    END:VCALENDAR
                """
            ),
            "1",
        ),
    ],
    ids=(
        "empty",
        "not_exists",
        "completed",
        "needs_action",
        "migrate_legacy_due",
        "due",
        "invalid_dtstart_tzname",
    ),
)
async def test_parse_existing_ics(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_integration: None,
    ws_get_items: Callable[[], Awaitable[dict[str, str]]],
    snapshot: SnapshotAssertion,
    expected_state: str,
) -> None:
    """Test parsing ics content."""

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state

    items = await ws_get_items()
    assert items == snapshot


async def test_susbcribe(
    hass: HomeAssistant,
    setup_integration: None,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribing to item updates."""

    # Create new item
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "soda"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
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

    # Rename item
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: uid, ATTR_RENAME: "milk"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
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
