"""Tests for todo platform of local_todo."""

from collections.abc import Callable, Coroutine
from datetime import datetime
import errno
import textwrap
from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
from ical.calendar_stream import IcsCalendarStream
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.local_todo import get_store
from homeassistant.components.local_todo.store import LocalTodoListStore
from homeassistant.components.todo import (
    ATTR_CATEGORY,
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
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import STORAGE_KEY, TEST_ENTITY, TODO_NAME

type WsGetItemsType = Callable[[], Coroutine[Any, Any, list[dict[str, str]]]]
type WsMoveItemType = Callable[[str, str | None], Coroutine[Any, Any, dict[str, Any]]]


@pytest.fixture
async def ws_get_items(hass_ws_client: WebSocketGenerator) -> WsGetItemsType:
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
async def ws_move_item(hass_ws_client: WebSocketGenerator) -> WsMoveItemType:
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
        return await client.receive_json()

    return move


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant) -> None:
    """Set the time zone for the tests that keeps UTC-6 all year round."""
    await hass.config.async_set_time_zone("America/Regina")


EXPECTED_ADD_ITEM = {
    "status": "needs_action",
    "summary": "replace batteries",
}


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(
            errno.EACCES, "os_write_permission_denied", id="permission_denied"
        ),
        pytest.param(errno.ENOSPC, "os_write_no_space", id="no_space"),
        pytest.param(errno.EROFS, "os_write_read_only", id="read_only"),
        pytest.param(errno.ENOENT, "os_write_dir_not_found", id="dir_not_found"),
        pytest.param(errno.EIO, "os_write_error", id="other"),
    ],
)
async def test_add_item_write_error(
    hass: HomeAssistant, error: int, translation_key: str
) -> None:
    """Test adding a todo item when the list can't be written."""
    with (
        patch.object(LocalTodoListStore, "_store", side_effect=OSError(error, "Error")),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "replace batteries"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )

    assert exc_info.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {
        "path": hass.config.path(f".storage/local_todo.{STORAGE_KEY}.ics")
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
        (
            {ATTR_CATEGORY: "Fresh produce"},
            {**EXPECTED_ADD_ITEM, "category": "Fresh produce"},
        ),
        ({ATTR_CATEGORY: None}, EXPECTED_ADD_ITEM),
        (
            {ATTR_ITEM: "测试主卧清扫"},
            {**EXPECTED_ADD_ITEM, "summary": "测试主卧清扫"},
        ),
    ],
)
async def test_add_item(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_integration: None,
    ws_get_items: WsGetItemsType,
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
    ws_get_items: WsGetItemsType,
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
    ws_get_items: WsGetItemsType,
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
            {
                **EXPECTED_UPDATE_ITEM,
                "status": "completed",
                "completed": "2023-11-18T08:00:00+00:00",
            },
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
        (
            {ATTR_CATEGORY: "Fresh produce"},
            {**EXPECTED_UPDATE_ITEM, "category": "Fresh produce"},
            "1",
        ),
    ],
)
async def test_update_item(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: WsGetItemsType,
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
    update_time = datetime(2023, 11, 18, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(update_time):
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
                "completed": "2023-11-18T08:00:00+00:00",
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
    ws_get_items: WsGetItemsType,
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
    update_time = datetime(2023, 11, 18, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(update_time):
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
    ws_get_items: WsGetItemsType,
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
    ws_get_items: WsGetItemsType,
    ws_move_item: WsMoveItemType,
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
    previous_uid = None if dst_idx is None else uids[dst_idx]
    resp = await ws_move_item(uids[src_idx], previous_uid)
    assert resp.get("success")

    items = await ws_get_items()
    assert len(items) == 4
    summaries = [item["summary"] for item in items]
    assert summaries == expected_items


async def test_move_item_unknown(
    hass: HomeAssistant,
    setup_integration: None,
    ws_move_item: WsMoveItemType,
) -> None:
    """Test moving a todo item that does not exist."""

    resp = await ws_move_item("unknown", "item-2")
    assert not resp.get("success")
    assert resp.get("error", {}).get("code") == "failed"
    assert "not found in to-do list" in resp["error"]["message"]


async def test_move_item_previous_unknown(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: WsGetItemsType,
    ws_move_item: WsMoveItemType,
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

    resp = await ws_move_item(items[0]["uid"], "unknown")
    assert not resp.get("success")
    assert resp.get("error", {}).get("code") == "failed"
    assert "not found in to-do list" in resp["error"]["message"]


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
                    COMPLETED:20231025T014011Z
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
    ws_get_items: WsGetItemsType,
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


async def test_reset_item_via_update(
    hass: HomeAssistant,
    setup_integration: None,
    ws_get_items: WsGetItemsType,
) -> None:
    """Test resetting a todo item via update action."""

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
    item_uid = item.pop("uid")

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    # Complete item
    update_time = datetime(2023, 11, 18, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(update_time):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: item_uid, ATTR_STATUS: "completed"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )

    # Verify item is completed
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert "uid" in item
    del item["uid"]
    assert item == {
        **EXPECTED_UPDATE_ITEM,
        "status": "completed",
        "completed": "2023-11-18T08:00:00+00:00",
    }

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    # Reset item
    update_time = datetime(2023, 11, 18, 8, 1, 0, tzinfo=dt_util.UTC)
    with freeze_time(update_time):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: item_uid, ATTR_STATUS: "needs_action"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )

    # Verify item is not completed
    items = await ws_get_items()
    assert len(items) == 1
    item = items[0]
    assert item["summary"] == "soda"
    assert item.get("completed") is None  # automatically unset
    assert "uid" in item
    del item["uid"]
    assert item == {
        **EXPECTED_UPDATE_ITEM,
        "status": "needs_action",
    }

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    ("ics_content", "expected_description"),
    [
        pytest.param(
            (
                "BEGIN:VCALENDAR\n"
                "PRODID:-//homeassistant.io//local_todo 2.0//EN\n"
                "VERSION:2.0\n"
                "BEGIN:VTODO\n"
                "DTSTAMP:20260205T183141Z\n"
                "UID:077cb7f2-6c89-11ee-b2a9-0242ac110002\n"
                "CREATED:20260205T183141Z\n"
                "SEQUENCE:0\n"
                "STATUS:NEEDS-ACTION\n"
                "SUMMARY:Notizen\n"
                "DESCRIPTION:Einkaufsliste\n\\nMilch\n\\nBrot\n"
                "END:VTODO\n"
                "END:VCALENDAR\n"
            ),
            "Einkaufsliste\nMilch\nBrot",
            id="universal_newlines",
        ),
        pytest.param(
            (
                "BEGIN:VCALENDAR\r\n"
                "PRODID:-//homeassistant.io//local_todo 2.0//EN\r\n"
                "VERSION:2.0\r\n"
                "BEGIN:VTODO\r\n"
                "DTSTAMP:20260205T183141Z\r\n"
                "UID:077cb7f2-6c89-11ee-b2a9-0242ac110002\r\n"
                "CREATED:20260205T183141Z\r\n"
                "SEQUENCE:0\r\n"
                "STATUS:NEEDS-ACTION\r\n"
                "SUMMARY:Notizen\r\n"
                "DESCRIPTION:Einkaufsliste\r\\nMilch\r\\nBrot\r\n"
                "END:VTODO\r\n"
                "END:VCALENDAR\r\n"
            ),
            "Einkaufsliste\nMilch\nBrot",
            id="raw_crlf",
        ),
        pytest.param(
            (
                "BEGIN:VCALENDAR\n"
                "PRODID:-//homeassistant.io//local_todo 2.0//EN\n"
                "VERSION:2.0\n"
                "BEGIN:VTODO\n"
                "DTSTAMP:20260205T183141Z\n"
                "UID:077cb7f2-6c89-11ee-b2a9-0242ac110002\n"
                "CREATED:20260205T183141Z\n"
                "SEQUENCE:0\n"
                "STATUS:NEEDS-ACTION\n"
                "SUMMARY:Notizen\n"
                "DESCRIPTION:Line 1\n\\n\n\\nLine 2\n"
                "END:VTODO\n"
                "END:VCALENDAR\n"
            ),
            "Line 1\n\nLine 2",
            id="consecutive_newlines",
        ),
    ],
)
async def test_repair_legacy_crlf_on_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
    caplog: pytest.LogCaptureFixture,
    expected_description: str,
) -> None:
    """Test repairing malformed ICS content from ical <= 12.1.3 CRLF bug on setup."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        f"Repaired malformed iCalendar file for to-do list {TODO_NAME}" in caplog.text
    )

    state = hass.states.get(TEST_ENTITY)
    assert state is not None
    assert state.state == "1"

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["summary"] == "Notizen"
    assert items[0]["description"] == expected_description

    # Verify that the file was re-saved cleanly to storage without any invalid lines
    store = config_entry.runtime_data.store
    re_saved = store._mock_path.read_text.return_value
    assert "\r" not in re_saved
    assert "\n\\n" not in re_saved


@pytest.mark.parametrize(
    "ics_content",
    [
        (
            "BEGIN:VCALENDAR\n"
            "PRODID:-//homeassistant.io//local_todo 1.0//EN\n"
            "VERSION:2.0\n"
            "BEGIN:VTODO\n"
            "DTSTAMP:20231024T014011\n"
            "UID:077cb7f2-6c89-11ee-b2a9-0242ac110002\n"
            "CREATED:20231017T010348\n"
            "SEQUENCE:1\n"
            "STATUS:NEEDS-ACTION\n"
            "SUMMARY:Task\n"
            "DESCRIPTION:Line 1\n\\nLine 2\n"
            "DUE:20231023\n"
            "END:VTODO\n"
            "END:VCALENDAR\n"
        )
    ],
)
async def test_repair_and_migrate_legacy_due_date(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that repaired legacy 1.0 calendars also undergo due date migration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        f"Repaired malformed iCalendar file for to-do list {TODO_NAME}" in caplog.text
    )

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["description"] == "Line 1\nLine 2"
    assert items[0]["due"] == "2023-10-23"

    store = config_entry.runtime_data.store
    re_saved = store._mock_path.read_text.return_value
    assert "PRODID:-//homeassistant.io//local_todo 2.0//EN" in re_saved
    assert "DUE;VALUE=DATE:20231024" in re_saved


async def test_description_newlines_preserved(
    hass: HomeAssistant,
    setup_integration: None,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
) -> None:
    """Test that newlines in descriptions are preserved through service calls and reload."""
    description = "Line 1\nLine 2\n\nLine 3"
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ITEM: "Item 1",
            ATTR_DESCRIPTION: description,
        },
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["description"] == description

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ITEM: items[0]["uid"],
            ATTR_DESCRIPTION: f"Updated\n{description}",
        },
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["description"] == f"Updated\n{description}"

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["description"] == f"Updated\n{description}"


async def test_crlf_description_preserved_on_reload(
    hass: HomeAssistant,
    setup_integration: None,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that items added with CRLF descriptions are saved cleanly and load on reload."""
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {
            ATTR_ITEM: "Item CRLF",
            ATTR_DESCRIPTION: "Line 1\r\nLine 2\r\n\r\nLine 3",
        },
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    # After reload from storage, newlines are preserved as LF and no repair warning is logged
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    items = await ws_get_items()
    assert len(items) == 1
    assert items[0]["description"] == "Line 1\nLine 2\n\nLine 3"
    assert "Repaired malformed iCalendar file" not in caplog.text


CATEGORIES_ICS = textwrap.dedent(
    """\
        BEGIN:VCALENDAR
        PRODID:-//homeassistant.io//local_todo 2.0//EN
        VERSION:2.0
        BEGIN:VTODO
        DTSTAMP:20231024T014011
        UID:apples
        SEQUENCE:1
        STATUS:NEEDS-ACTION
        SUMMARY:Apples
        CATEGORIES:Fresh produce,Organic
        END:VTODO
        BEGIN:VTODO
        DTSTAMP:20231024T014011
        UID:pasta
        SEQUENCE:1
        STATUS:NEEDS-ACTION
        SUMMARY:Pasta
        CATEGORIES:Grocery
        END:VTODO
        BEGIN:VTODO
        DTSTAMP:20231024T014011
        UID:soap
        SEQUENCE:1
        STATUS:NEEDS-ACTION
        SUMMARY:Soap
        END:VTODO
        END:VCALENDAR
    """
)


async def _stored_categories(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[list[str]]:
    """Return the categories of the items persisted in the store."""
    store = get_store(hass, config_entry)
    calendar = IcsCalendarStream.calendar_from_ics(await store.async_load())
    return [todo.categories for todo in calendar.todos]


@pytest.mark.parametrize(
    ("item_data", "expected_category", "expected_categories"),
    [
        pytest.param(
            {ATTR_CATEGORY: "Household"}, "Household", ["Household"], id="change"
        ),
        pytest.param(
            {ATTR_STATUS: "completed"},
            "Fresh produce",
            ["Fresh produce"],
            id="unrelated_update",
        ),
        pytest.param({ATTR_CATEGORY: None}, None, [], id="clear"),
    ],
)
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_update_category_stored_as_categories(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
    item_data: dict[str, Any],
    expected_category: str | None,
    expected_categories: list[str],
) -> None:
    """Test the category is stored as the only category of the item."""
    items = await ws_get_items()
    assert items[0]["category"] == "Fresh produce"

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "Apples", **item_data},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    items = await ws_get_items()
    assert items[0].get("category") == expected_category
    assert (await _stored_categories(hass, config_entry))[0] == expected_categories


@pytest.mark.parametrize(
    ("service", "item_data"),
    [
        pytest.param(TodoServices.ADD_ITEM, {ATTR_ITEM: "Pears"}, id="add"),
        pytest.param(TodoServices.UPDATE_ITEM, {ATTR_ITEM: "Apples"}, id="update"),
    ],
)
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_category_with_comma(
    hass: HomeAssistant, service: TodoServices, item_data: dict[str, Any]
) -> None:
    """Test a category can't contain a comma, as it doesn't survive a reload."""
    with pytest.raises(ServiceValidationError, match="can't contain a comma"):
        await hass.services.async_call(
            TODO_DOMAIN,
            service,
            {**item_data, ATTR_CATEGORY: "Fruits, vegetables"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("categories", "expected_categories"),
    [
        pytest.param(
            ["Fresh produce", "Grocery", "Household"],
            ["Fresh produce", "Grocery", "Household"],
            id="categories",
        ),
        pytest.param([], None, id="empty"),
        pytest.param(None, None, id="no_options"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_categories_attribute(
    hass: HomeAssistant, expected_categories: list[str] | None
) -> None:
    """Test the categories attribute comes from the options."""
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.attributes.get("categories") == expected_categories


async def _set_categories(
    hass: HomeAssistant, entry_id: str, categories: list[str]
) -> None:
    """Set the categories with the options flow."""
    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "categories"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"categories": categories}
    )
    await hass.async_block_till_done()


async def _remove_fresh_produce(hass: HomeAssistant, entry_id: str) -> None:
    """Remove the Fresh produce category with the options flow."""
    await _set_categories(hass, entry_id, ["Grocery", "Household"])


async def _rename_fresh_produce(hass: HomeAssistant, entry_id: str) -> None:
    """Rename the Fresh produce category to Produce with the options flow."""
    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "rename_category"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"category": "Fresh produce", "new_name": "Produce"}
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_remove_category(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
) -> None:
    """Test removing a category leaves its items without a category."""
    await _remove_fresh_produce(hass, config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.attributes["categories"] == ["Grocery", "Household"]
    items = await ws_get_items()
    assert {item["summary"]: item.get("category") for item in items} == {
        "Apples": None,
        "Pasta": "Grocery",
        "Soap": None,
    }
    assert await _stored_categories(hass, config_entry) == [[], ["Grocery"], []]


@pytest.mark.parametrize(
    ("change_categories", "expected_options", "expected_categories"),
    [
        pytest.param(
            _remove_fresh_produce,
            ["Grocery", "Household"],
            [[], ["Grocery"], []],
            id="remove",
        ),
        pytest.param(
            _rename_fresh_produce,
            ["Produce", "Grocery", "Household"],
            [["Produce"], ["Grocery"], []],
            id="rename",
        ),
    ],
)
@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_category_change_entry_not_loaded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    change_categories: Callable[[HomeAssistant, str], Coroutine[Any, Any, None]],
    expected_options: list[str],
    expected_categories: list[list[str]],
) -> None:
    """Test items are updated even when the entry isn't loaded."""
    await hass.config_entries.async_unload(config_entry.entry_id)

    await change_categories(hass, config_entry.entry_id)

    assert config_entry.options == {"categories": expected_options}
    assert await _stored_categories(hass, config_entry) == expected_categories


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_rename_category(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
) -> None:
    """Test renaming a category keeps its items in it."""
    await _rename_fresh_produce(hass, config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.attributes["categories"] == ["Produce", "Grocery", "Household"]
    items = await ws_get_items()
    assert {item["summary"]: item.get("category") for item in items} == {
        "Apples": "Produce",
        "Pasta": "Grocery",
        "Soap": None,
    }
    assert await _stored_categories(hass, config_entry) == [
        ["Produce"],
        ["Grocery"],
        [],
    ]


async def _unload_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Unload the entry."""
    await hass.config_entries.async_unload(config_entry.entry_id)


async def _keep_entry_loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Leave the entry loaded."""


@pytest.mark.parametrize(
    "prepare_entry",
    [
        pytest.param(_keep_entry_loaded, id="loaded"),
        pytest.param(_unload_entry, id="not_loaded"),
    ],
)
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_options_offer_item_categories(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    prepare_entry: Callable[
        [HomeAssistant, MockConfigEntry], Coroutine[Any, Any, None]
    ],
) -> None:
    """Test categories used by items are offered even when they aren't declared."""
    await prepare_entry(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "categories"}
    )
    schema = result["data_schema"].schema
    suggested = next(iter(schema)).description["suggested_value"]
    assert suggested == ["Fresh produce", "Grocery"]


@pytest.mark.parametrize(
    ("change_categories", "expected_options", "expected_categories"),
    [
        pytest.param(
            _remove_fresh_produce,
            ["Grocery", "Household"],
            [[], ["Grocery"], []],
            id="remove",
        ),
        pytest.param(
            _rename_fresh_produce,
            [],
            [["Produce"], ["Grocery"], []],
            id="rename",
        ),
    ],
)
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_change_undeclared_category(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ws_get_items: WsGetItemsType,
    change_categories: Callable[[HomeAssistant, str], Coroutine[Any, Any, None]],
    expected_options: list[str],
    expected_categories: list[list[str]],
) -> None:
    """Test a category only used by items can be renamed or removed."""
    await change_categories(hass, config_entry.entry_id)

    assert config_entry.options == {"categories": expected_options}
    assert await _stored_categories(hass, config_entry) == expected_categories


@pytest.mark.parametrize(
    "prepare_entry",
    [
        pytest.param(_keep_entry_loaded, id="loaded"),
        pytest.param(_unload_entry, id="not_loaded"),
    ],
)
@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_remove_category_write_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    prepare_entry: Callable[
        [HomeAssistant, MockConfigEntry], Coroutine[Any, Any, None]
    ],
) -> None:
    """Test the options are kept when the items can't be updated."""
    await prepare_entry(hass, config_entry)

    with (
        patch.object(
            LocalTodoListStore, "_store", side_effect=OSError(errno.EIO, "Error")
        ),
        pytest.raises(HomeAssistantError),
    ):
        await _remove_fresh_produce(hass, config_entry.entry_id)

    assert config_entry.options == {
        "categories": ["Fresh produce", "Grocery", "Household"]
    }


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_item_save_after_category_change(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test saving an item doesn't bring back a renamed category."""
    await _rename_fresh_produce(hass, config_entry.entry_id)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "Pasta", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    assert await _stored_categories(hass, config_entry) == [
        ["Produce"],
        ["Grocery"],
        [],
    ]


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_subscription_after_category_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test item subscriptions keep receiving updates after a category change."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/subscribe", "entity_id": TEST_ENTITY}
    )
    msg = await client.receive_json()
    assert msg["success"]
    msg = await client.receive_json()
    assert msg["event"]["items"][0]["category"] == "Fresh produce"

    await _rename_fresh_produce(hass, config_entry.entry_id)

    msg = await client.receive_json()
    assert msg["event"]["items"][0]["category"] == "Produce"

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Pears", ATTR_CATEGORY: "Produce"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    msg = await client.receive_json()
    assert [item["summary"] for item in msg["event"]["items"]] == [
        "Apples",
        "Pasta",
        "Soap",
        "Pears",
    ]


@pytest.mark.parametrize(
    ("change_categories", "expected_options", "expected_categories"),
    [
        pytest.param(
            _remove_fresh_produce,
            ["Grocery", "Household"],
            [[], ["Grocery"], []],
            id="remove",
        ),
        pytest.param(
            _rename_fresh_produce,
            ["Produce", "Grocery", "Household"],
            [["Produce"], ["Grocery"], []],
            id="rename",
        ),
    ],
)
@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
async def test_category_change_entity_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    change_categories: Callable[[HomeAssistant, str], Coroutine[Any, Any, None]],
    expected_options: list[str],
    expected_categories: list[list[str]],
) -> None:
    """Test items are updated on disk when the entity is disabled."""
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "todo",
        "local_todo",
        config_entry.entry_id,
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.entity is None

    await change_categories(hass, config_entry.entry_id)

    assert config_entry.options == {"categories": expected_options}
    assert await _stored_categories(hass, config_entry) == expected_categories


LEGACY_CRLF_CATEGORIES_ICS = (
    "BEGIN:VCALENDAR\n"
    "PRODID:-//homeassistant.io//local_todo 2.0//EN\n"
    "VERSION:2.0\n"
    "BEGIN:VTODO\n"
    "DTSTAMP:20260205T183141Z\n"
    "UID:apples\n"
    "SEQUENCE:0\n"
    "STATUS:NEEDS-ACTION\n"
    "SUMMARY:Apples\n"
    "CATEGORIES:Fresh produce\n"
    "DESCRIPTION:Line 1\n\\n\n\\nLine 2\n"
    "END:VTODO\n"
    "END:VCALENDAR\n"
)


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [LEGACY_CRLF_CATEGORIES_ICS])
async def test_remove_category_legacy_file_entry_not_loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test categories can be removed from a malformed legacy file not loaded yet."""
    config_entry.add_to_hass(hass)

    await _remove_fresh_produce(hass, config_entry.entry_id)

    assert config_entry.options == {"categories": ["Grocery", "Household"]}
    assert await _stored_categories(hass, config_entry) == [[]]


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.parametrize("ics_content", [CATEGORIES_ICS])
@pytest.mark.usefixtures("setup_integration")
async def test_category_change_write_error_keeps_items(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a failed category change isn't saved by a later item change."""
    with (
        patch.object(
            LocalTodoListStore, "_store", side_effect=OSError(errno.EIO, "Error")
        ),
        pytest.raises(HomeAssistantError),
    ):
        await _remove_fresh_produce(hass, config_entry.entry_id)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "Pasta", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    assert await _stored_categories(hass, config_entry) == [
        ["Fresh produce", "Organic"],
        ["Grocery"],
        [],
    ]


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery", "Household"]])
@pytest.mark.usefixtures("setup_integration")
async def test_categories_attribute_follows_options(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reordering or clearing categories updates the loaded list."""
    await _set_categories(
        hass, config_entry.entry_id, ["Household", "Fresh produce", "Grocery"]
    )
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.attributes["categories"] == ["Household", "Fresh produce", "Grocery"]

    await _set_categories(hass, config_entry.entry_id, [])
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert "categories" not in state.attributes
