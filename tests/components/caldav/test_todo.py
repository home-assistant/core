"""The tests for the webdav todo component."""

import asyncio
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock, Mock

from caldav.calendarobjectresource import Todo
from caldav.collection import SynchronizableCalendarObjectCollection
from caldav.lib.error import DAVError, NotFoundError
from caldav.lib.http_sync import requests as caldav_requests
from caldav.lib.url import URL
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

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
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import async_update_entity

CALENDAR_NAME = "My Tasks"
ENTITY_NAME = "My tasks"
TEST_ENTITY = "todo.my_tasks"
SUPPORTED_FEATURES = 119

TODO_NO_STATUS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:1
DTSTAMP:20231125T000000Z
SUMMARY:Milk
END:VTODO
END:VCALENDAR"""

TODO_NEEDS_ACTION = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:2
DTSTAMP:20171125T000000Z
SUMMARY:Cheese
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

RESULT_ITEM = {
    "uid": "2",
    "summary": "Cheese",
    "status": "needs_action",
}

TODO_COMPLETED = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:3
DTSTAMP:20231125T000000Z
SUMMARY:Wine
STATUS:COMPLETED
END:VTODO
END:VCALENDAR"""

TODO_COMPLETED_AT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:3
DTSTAMP:20231125T000000Z
SUMMARY:Wine
STATUS:COMPLETED
COMPLETED:20231125T120000Z
END:VTODO
END:VCALENDAR"""


TODO_NO_SUMMARY = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:4
DTSTAMP:20171126T000000Z
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""

TODO_ALL_FIELDS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:2
DTSTAMP:20171125T000000Z
SUMMARY:Cheese
DESCRIPTION:Any kind will do
STATUS:NEEDS-ACTION
DUE:20171126
END:VTODO
END:VCALENDAR"""


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set up config entry platforms."""
    return [Platform.TODO]


@pytest.fixture(autouse=True)
async def set_tz(hass: HomeAssistant) -> None:
    """Fixture to set timezone with fixed offset year round."""
    await hass.config.async_set_time_zone("America/Regina")


@pytest.fixture(name="todos")
def mock_todos() -> list[str]:
    """Fixture to return VTODO objects for the calendar."""
    return []


@pytest.fixture(name="supported_components")
def mock_supported_components() -> list[str]:
    """Fixture to set supported components of the calendar."""
    return ["VTODO"]


def sync_report(
    sync_token: str | None, changes: int = 0
) -> SynchronizableCalendarObjectCollection:
    """Return a sync-collection report listing a number of changed items."""
    return SynchronizableCalendarObjectCollection(
        calendar=None,
        objects=[Todo(url=f"{idx}.ics") for idx in range(changes)],
        sync_token=sync_token,
    )


@pytest.fixture(name="calendar")
def mock_calendar(supported_components: list[str]) -> Mock:
    """Fixture to create the primary calendar for the test."""
    calendar = Mock()
    calendar.client = None
    calendar.url = URL("https://example.com/calendar/")
    calendar.search = MagicMock(return_value=[])
    calendar.get_display_name = MagicMock(return_value=CALENDAR_NAME)
    calendar.get_supported_components = MagicMock(return_value=supported_components)
    calendar.get_objects_by_sync_token = MagicMock(return_value=sync_report(None))
    return calendar


def create_todo(calendar: Mock, idx: str, ics: str) -> Todo:
    """Create a caldav Todo object."""
    return Todo(client=None, url=f"{idx}.ics", data=ics, parent=calendar, id=idx)


@pytest.fixture(autouse=True)
def mock_search_items(calendar: Mock, todos: list[str]) -> None:
    """Fixture to add search results to the test calendar."""
    calendar.search.return_value = [
        create_todo(calendar, str(idx), item) for idx, item in enumerate(todos)
    ]


@pytest.fixture(name="calendars")
def mock_calendars(calendar: Mock) -> list[Mock]:
    """Fixture to create calendars for the test."""
    return [calendar]


@pytest.fixture(autouse=True)
async def mock_add_to_hass(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Fixture to add the ConfigEntry."""
    config_entry.add_to_hass(hass)


IGNORE_COMPONENTS = ["BEGIN", "END", "DTSTAMP", "PRODID", "UID", "VERSION"]


def compact_ics(ics: str) -> list[str]:
    """Pull out parts of the rfc5545 content useful for assertions in tests."""
    return [
        line
        for line in ics.split("\n")
        if line and not any(filter(line.startswith, IGNORE_COMPONENTS))
    ]


@pytest.mark.parametrize(
    ("todos", "expected_state"),
    [
        ([], "0"),
        (
            [TODO_NEEDS_ACTION],
            "1",
        ),
        (
            [TODO_NO_STATUS],
            "1",
        ),
        ([TODO_COMPLETED], "0"),
        ([TODO_NO_STATUS, TODO_NEEDS_ACTION, TODO_COMPLETED], "2"),
        ([TODO_NO_SUMMARY], "0"),
    ],
    ids=(
        "empty",
        "needs_action",
        "no_status",
        "completed",
        "all",
        "no_summary",
    ),
)
async def test_todo_list_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    expected_state: str,
) -> None:
    """Test a calendar entity from a config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == ENTITY_NAME
    assert state.state == expected_state
    assert dict(state.attributes) == {
        "friendly_name": ENTITY_NAME,
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize(
    ("todos", "expected_item"),
    [
        (
            [TODO_COMPLETED_AT],
            {
                "uid": "0",
                "summary": "Wine",
                "status": "completed",
                "completed": "2023-11-25T06:00:00-06:00",
            },
        ),
        (
            [TODO_COMPLETED],
            {"uid": "0", "summary": "Wine", "status": "completed"},
        ),
        (
            [TODO_COMPLETED_AT.replace("STATUS:COMPLETED", "STATUS:NEEDS-ACTION")],
            {"uid": "0", "summary": "Wine", "status": "needs_action"},
        ),
    ],
    ids=["completed_at", "no_completed", "reopened"],
)
async def test_completed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    expected_item: dict[str, Any],
) -> None:
    """Test the time a to-do item was completed is read from the server."""
    await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
        return_response=True,
    )
    assert result == {TEST_ENTITY: {"items": [expected_item]}}


@pytest.mark.parametrize(
    ("supported_components", "has_entity"),
    [([], False), (["VTODO"], True), (["VEVENT"], False), (["VEVENT", "VTODO"], True)],
)
async def test_supported_components(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    has_entity: bool,
) -> None:
    """Test a calendar supported components matches VTODO."""
    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert (state is not None) == has_entity


@pytest.mark.parametrize(
    ("item_data", "expcted_save_args", "expected_item"),
    [
        (
            {},
            {"status": "NEEDS-ACTION", "summary": "Cheese"},
            RESULT_ITEM,
        ),
        (
            {ATTR_DUE_DATE: "2023-11-18"},
            {"status": "NEEDS-ACTION", "summary": "Cheese", "due": date(2023, 11, 18)},
            {**RESULT_ITEM, "due": "2023-11-18"},
        ),
        (
            {ATTR_DUE_DATETIME: "2023-11-18T08:30:00-06:00"},
            {
                "status": "NEEDS-ACTION",
                "summary": "Cheese",
                "due": datetime(2023, 11, 18, 14, 30, 00, tzinfo=UTC),
            },
            {**RESULT_ITEM, "due": "2023-11-18T08:30:00-06:00"},
        ),
        (
            {ATTR_DESCRIPTION: "Make sure to get Swiss"},
            {
                "status": "NEEDS-ACTION",
                "summary": "Cheese",
                "description": "Make sure to get Swiss",
            },
            {**RESULT_ITEM, "description": "Make sure to get Swiss"},
        ),
    ],
    ids=[
        "summary",
        "due_date",
        "due_datetime",
        "description",
    ],
)
async def test_add_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    item_data: dict[str, Any],
    expcted_save_args: dict[str, Any],
    expected_item: dict[str, Any],
) -> None:
    """Test adding an item to the list."""
    calendar.search.return_value = []
    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    # Simulate return value for the state update after the service call
    calendar.search.return_value = [create_todo(calendar, "2", TODO_NEEDS_ACTION)]

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Cheese", **item_data},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )
    # Wait for the fire-and-forget state refresh
    await hass.async_block_till_done()

    assert calendar.add_todo.call_args
    assert calendar.add_todo.call_args.kwargs == expcted_save_args

    # Verify state was updated
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


async def test_add_item_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
) -> None:
    """Test failure when adding an item to the list."""
    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.add_todo.side_effect = DAVError()

    with pytest.raises(HomeAssistantError, match="CalDAV save error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "Cheese"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


@pytest.mark.freeze_time("2023-11-25 12:00:00+00:00")
@pytest.mark.parametrize(
    ("update_data", "expected_ics", "expected_state", "expected_item"),
    [
        (
            {ATTR_RENAME: "Swiss Cheese"},
            [
                "DESCRIPTION:Any kind will do",
                "DUE;VALUE=DATE:20171126",
                "STATUS:NEEDS-ACTION",
                "SUMMARY:Swiss Cheese",
            ],
            "1",
            {
                "uid": "2",
                "summary": "Swiss Cheese",
                "status": "needs_action",
                "description": "Any kind will do",
                "due": "2017-11-26",
            },
        ),
        (
            {ATTR_STATUS: "needs_action"},
            [
                "DESCRIPTION:Any kind will do",
                "DUE;VALUE=DATE:20171126",
                "STATUS:NEEDS-ACTION",
                "SUMMARY:Cheese",
            ],
            "1",
            {
                "uid": "2",
                "summary": "Cheese",
                "status": "needs_action",
                "description": "Any kind will do",
                "due": "2017-11-26",
            },
        ),
        (
            {ATTR_STATUS: "completed"},
            [
                "COMPLETED:20231125T120000Z",
                "DESCRIPTION:Any kind will do",
                "DUE;VALUE=DATE:20171126",
                "STATUS:COMPLETED",
                "SUMMARY:Cheese",
            ],
            "0",
            {
                "uid": "2",
                "summary": "Cheese",
                "status": "completed",
                "description": "Any kind will do",
                "due": "2017-11-26",
                "completed": "2023-11-25T06:00:00-06:00",
            },
        ),
        (
            {ATTR_RENAME: "Swiss Cheese", ATTR_STATUS: "needs_action"},
            [
                "DESCRIPTION:Any kind will do",
                "DUE;VALUE=DATE:20171126",
                "STATUS:NEEDS-ACTION",
                "SUMMARY:Swiss Cheese",
            ],
            "1",
            {
                "uid": "2",
                "summary": "Swiss Cheese",
                "status": "needs_action",
                "description": "Any kind will do",
                "due": "2017-11-26",
            },
        ),
        (
            {ATTR_DUE_DATE: "2023-11-18"},
            [
                "DESCRIPTION:Any kind will do",
                "DUE;VALUE=DATE:20231118",
                "STATUS:NEEDS-ACTION",
                "SUMMARY:Cheese",
            ],
            "1",
            {
                "uid": "2",
                "summary": "Cheese",
                "status": "needs_action",
                "description": "Any kind will do",
                "due": "2023-11-18",
            },
        ),
        (
            {ATTR_DUE_DATETIME: "2023-11-18T08:30:00-06:00"},
            [
                "DESCRIPTION:Any kind will do",
                "DUE;TZID=America/Regina:20231118T083000",
                "STATUS:NEEDS-ACTION",
                "SUMMARY:Cheese",
            ],
            "1",
            {
                "uid": "2",
                "summary": "Cheese",
                "status": "needs_action",
                "description": "Any kind will do",
                "due": "2023-11-18T08:30:00-06:00",
            },
        ),
        (
            {ATTR_DUE_DATETIME: None},
            [
                "DESCRIPTION:Any kind will do",
                "STATUS:NEEDS-ACTION",
                "SUMMARY:Cheese",
            ],
            "1",
            {
                "uid": "2",
                "summary": "Cheese",
                "status": "needs_action",
                "description": "Any kind will do",
            },
        ),
        (
            {ATTR_DESCRIPTION: "Make sure to get Swiss"},
            [
                "DESCRIPTION:Make sure to get Swiss",
                "DUE;VALUE=DATE:20171126",
                "STATUS:NEEDS-ACTION",
                "SUMMARY:Cheese",
            ],
            "1",
            {
                "uid": "2",
                "summary": "Cheese",
                "status": "needs_action",
                "due": "2017-11-26",
                "description": "Make sure to get Swiss",
            },
        ),
        (
            {ATTR_DESCRIPTION: None},
            ["DUE;VALUE=DATE:20171126", "STATUS:NEEDS-ACTION", "SUMMARY:Cheese"],
            "1",
            {
                "uid": "2",
                "summary": "Cheese",
                "status": "needs_action",
                "due": "2017-11-26",
            },
        ),
    ],
    ids=[
        "rename",
        "status_needs_action",
        "status_completed",
        "rename_status",
        "due_date",
        "due_datetime",
        "clear_due_date",
        "description",
        "clear_description",
    ],
)
async def test_update_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    update_data: dict[str, Any],
    expected_ics: list[str],
    expected_state: str,
    expected_item: dict[str, Any],
) -> None:
    """Test updating an item on the list."""

    item = Todo(dav_client, None, TODO_ALL_FIELDS, calendar, "2")
    calendar.search = MagicMock(return_value=[item])

    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    calendar.get_todo_by_uid = MagicMock(return_value=item)

    dav_client.put.return_value.status = 204

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ITEM: "Cheese",
            **update_data,
        },
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )
    # Wait for the fire-and-forget state refresh
    await hass.async_block_till_done()

    assert dav_client.put.call_args
    ics = dav_client.put.call_args.args[1]
    assert compact_ics(ics) == expected_ics

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
        return_response=True,
    )
    assert result == {TEST_ENTITY: {"items": [expected_item]}}


@pytest.mark.freeze_time("2024-01-02 03:04:05+00:00")
@pytest.mark.parametrize(
    ("ics", "update_data", "expected_ics"),
    [
        (
            TODO_COMPLETED_AT,
            {ATTR_RENAME: "Red Wine"},
            ["COMPLETED:20231125T120000Z", "STATUS:COMPLETED", "SUMMARY:Red Wine"],
        ),
        (
            TODO_COMPLETED_AT,
            {ATTR_STATUS: "needs_action"},
            ["STATUS:NEEDS-ACTION", "SUMMARY:Wine"],
        ),
        (
            TODO_COMPLETED_AT.replace("STATUS:COMPLETED", "STATUS:NEEDS-ACTION"),
            {ATTR_RENAME: "Red Wine"},
            ["STATUS:NEEDS-ACTION", "SUMMARY:Red Wine"],
        ),
        (
            TODO_COMPLETED_AT.replace("STATUS:COMPLETED", "STATUS:NEEDS-ACTION"),
            {ATTR_STATUS: "completed"},
            ["COMPLETED:20240102T030405Z", "STATUS:COMPLETED", "SUMMARY:Wine"],
        ),
        (
            TODO_COMPLETED.replace("STATUS:COMPLETED", "STATUS:CANCELLED"),
            {ATTR_RENAME: "Red Wine"},
            ["STATUS:COMPLETED", "SUMMARY:Red Wine"],
        ),
    ],
    ids=[
        "rename_completed",
        "reopen",
        "rename_stale",
        "complete_stale",
        "rename_cancelled",
    ],
)
async def test_update_item_completed_time(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    ics: str,
    update_data: dict[str, Any],
    expected_ics: list[str],
) -> None:
    """Test the completed time is kept, set or removed when updating an item."""

    item = Todo(dav_client, None, ics, calendar, "3")
    calendar.search = MagicMock(return_value=[item])
    calendar.get_todo_by_uid = MagicMock(return_value=item)
    dav_client.put.return_value.status = 204

    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "Wine", **update_data},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert dav_client.put.call_count == 1
    assert compact_ics(dav_client.put.call_args.args[1]) == expected_ics


async def test_update_item_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
) -> None:
    """Test failure when updating an item on the list."""

    item = Todo(dav_client, None, TODO_NEEDS_ACTION, calendar, "2")
    calendar.search = MagicMock(return_value=[item])

    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.get_todo_by_uid = MagicMock(return_value=item)
    dav_client.put.side_effect = DAVError()

    with pytest.raises(HomeAssistantError, match="CalDAV save error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {
                ATTR_ITEM: "Cheese",
                ATTR_STATUS: "completed",
            },
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("side_effect", "match"),
    [(DAVError, "CalDAV lookup error"), (NotFoundError, "Could not find")],
)
async def test_update_item_lookup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    side_effect: Any,
    match: str,
) -> None:
    """Test failure when looking up an item to update."""

    item = Todo(dav_client, None, TODO_NEEDS_ACTION, calendar, "2")
    calendar.search = MagicMock(return_value=[item])

    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.get_todo_by_uid.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {
                ATTR_ITEM: "Cheese",
                ATTR_STATUS: "completed",
            },
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("uids_to_delete", "expect_item1_delete_called", "expect_item2_delete_called"),
    [
        ([], False, False),
        (["Cheese"], True, False),
        (["Wine"], False, True),
        (["Wine", "Cheese"], True, True),
    ],
    ids=("none", "item1-only", "item2-only", "both-items"),
)
async def test_remove_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    uids_to_delete: list[str],
    expect_item1_delete_called: bool,
    expect_item2_delete_called: bool,
) -> None:
    """Test removing an item on the list."""

    item1 = Todo(dav_client, None, TODO_NEEDS_ACTION, calendar, "2")
    item2 = Todo(dav_client, None, TODO_COMPLETED, calendar, "3")
    calendar.search = MagicMock(return_value=[item1, item2])

    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"

    def lookup(uid: str) -> Mock:
        assert uid in ("2", "3")
        if uid == "2":
            return item1
        return item2

    calendar.get_todo_by_uid = Mock(side_effect=lookup)
    item1.delete = Mock()
    item2.delete = Mock()

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: uids_to_delete},
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    assert item1.delete.called == expect_item1_delete_called
    assert item2.delete.called == expect_item2_delete_called


@pytest.mark.parametrize(
    ("todos", "side_effect", "match"),
    [
        ([TODO_NEEDS_ACTION], DAVError, "CalDAV lookup error"),
        ([TODO_NEEDS_ACTION], NotFoundError, "Could not find"),
    ],
)
async def test_remove_item_lookup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    side_effect: Any,
    match: str,
) -> None:
    """Test failure while removing an item from the list."""

    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.get_todo_by_uid.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: "Cheese"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


async def test_remove_item_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
) -> None:
    """Test removing an item on the list."""

    item = Todo(dav_client, "2.ics", TODO_NEEDS_ACTION, calendar, "2")
    calendar.search = MagicMock(return_value=[item])

    await hass.config_entries.async_setup(config_entry.entry_id)

    def lookup(uid: str) -> Mock:
        return item

    calendar.get_todo_by_uid = Mock(side_effect=lookup)
    dav_client.delete.return_value.status = 500

    with pytest.raises(HomeAssistantError, match="CalDAV delete error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: "Cheese"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


async def test_remove_item_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
) -> None:
    """Test removing an item on the list."""

    item = Todo(dav_client, "2.ics", TODO_NEEDS_ACTION, calendar, "2")
    calendar.search = MagicMock(return_value=[item])

    await hass.config_entries.async_setup(config_entry.entry_id)

    def lookup(uid: str) -> Mock:
        return item

    calendar.get_todo_by_uid.side_effect = NotFoundError()

    with pytest.raises(HomeAssistantError, match="Could not find"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: "Cheese"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


async def test_subscribe(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscription to item updates."""

    item = Todo(dav_client, None, TODO_NEEDS_ACTION, calendar, "2")
    calendar.search = MagicMock(return_value=[item])

    await hass.config_entries.async_setup(config_entry.entry_id)

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
    assert items[0]["summary"] == "Cheese"
    assert items[0]["status"] == "needs_action"
    assert items[0]["uid"]

    calendar.get_todo_by_uid = MagicMock(return_value=item)
    dav_client.put.return_value.status = 204
    # Reflect update for state refresh after update
    calendar.search.return_value = [
        Todo(
            dav_client, None, TODO_NEEDS_ACTION.replace("Cheese", "Milk"), calendar, "2"
        )
    ]
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ITEM: "Cheese",
            ATTR_RENAME: "Milk",
        },
        target={ATTR_ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()

    # An earlier state write may re-publish the pre-update list; read until the
    # refreshed item arrives.
    items = []
    while not items or items[0]["summary"] != "Milk":
        msg = await client.receive_json()
        assert msg["id"] == subscription_id
        assert msg["type"] == "event"
        items = msg["event"].get("items")

    assert len(items) == 1
    assert items[0]["summary"] == "Milk"
    assert items[0]["status"] == "needs_action"
    assert items[0]["uid"]


@pytest.mark.parametrize(
    ("reports", "expected_state", "next_token"),
    [
        pytest.param(
            [sync_report("token-1"), sync_report("token-1")],
            "0",
            "token-1",
            id="unchanged",
        ),
        pytest.param(
            [sync_report("token-1"), sync_report("token-2")],
            "1",
            "token-2",
            id="new_token",
        ),
        pytest.param(
            [sync_report("token-1"), sync_report("token-1", changes=1)],
            "1",
            "token-1",
            id="listed_change",
        ),
        pytest.param([sync_report(None), sync_report(None)], "1", None, id="no_token"),
        pytest.param(
            [sync_report("token-1"), DAVError()], "1", None, id="rejected_token"
        ),
        pytest.param([DAVError(), DAVError()], "1", None, id="no_sync_report"),
        pytest.param(
            [sync_report("token-1"), caldav_requests.exceptions.ConnectionError()],
            "1",
            None,
            id="report_connection_error",
        ),
        pytest.param(
            [sync_report("token-1"), caldav_requests.exceptions.Timeout()],
            "1",
            None,
            id="report_timeout",
        ),
        pytest.param(
            [sync_report("token-1"), caldav_requests.exceptions.ChunkedEncodingError()],
            "1",
            None,
            id="report_cut_off",
        ),
    ],
)
async def test_update_after_sync_report(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    reports: list[SynchronizableCalendarObjectCollection | Exception],
    expected_state: str,
    next_token: str | None,
) -> None:
    """Test the list is read again unless the server reports no change."""
    calendar.get_objects_by_sync_token.side_effect = [*reports, sync_report(None)]
    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.search.return_value = [create_todo(calendar, "1", TODO_NEEDS_ACTION)]
    await async_update_entity(hass, TEST_ENTITY)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state

    await async_update_entity(hass, TEST_ENTITY)
    calendar.get_objects_by_sync_token.assert_called_with(
        next_token, disable_fallback=True
    )


@pytest.mark.parametrize(
    ("server_todos", "expected_state", "next_token", "next_reads"),
    [
        pytest.param([], "0", "token-1", 2, id="unchanged"),
        pytest.param([TODO_NEEDS_ACTION], "1", None, 3, id="missed_change"),
    ],
)
async def test_update_reads_in_full_every_fourth_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server_todos: list[str],
    expected_state: str,
    next_token: str | None,
    next_reads: int,
) -> None:
    """Test the list is read in full every fourth update without a reported change."""
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.search.return_value = [
        create_todo(calendar, str(idx), item) for idx, item in enumerate(server_todos)
    ]
    for _ in range(3):
        await async_update_entity(hass, TEST_ENTITY)
    assert calendar.search.call_count == 1

    await async_update_entity(hass, TEST_ENTITY)
    assert calendar.search.call_count == 2
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state

    await async_update_entity(hass, TEST_ENTITY)
    calendar.get_objects_by_sync_token.assert_called_with(
        next_token, disable_fallback=True
    )
    assert calendar.search.call_count == next_reads


@pytest.mark.parametrize(
    ("reports", "skipped_updates"),
    [
        pytest.param(
            [sync_report("token-1"), sync_report("token-2"), sync_report("token-2")],
            0,
            id="new_token",
        ),
        pytest.param([sync_report("token-1")] * 6, 3, id="fourth_update"),
    ],
)
async def test_update_after_failed_read(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    reports: list[SynchronizableCalendarObjectCollection],
    skipped_updates: int,
) -> None:
    """Test a failed read is retried on the next update."""
    calendar.get_objects_by_sync_token.side_effect = reports
    await hass.config_entries.async_setup(config_entry.entry_id)
    for _ in range(skipped_updates):
        await async_update_entity(hass, TEST_ENTITY)

    calendar.search.side_effect = DAVError
    await async_update_entity(hass, TEST_ENTITY)

    calendar.search.side_effect = None
    calendar.search.return_value = [create_todo(calendar, "1", TODO_NEEDS_ACTION)]
    await async_update_entity(hass, TEST_ENTITY)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    ("service", "data", "todos_after", "expected_state"),
    [
        pytest.param(
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "Milk"},
            [TODO_NEEDS_ACTION, TODO_NO_STATUS],
            "2",
            id="add",
        ),
        pytest.param(
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "Cheese", ATTR_STATUS: "completed"},
            [TODO_COMPLETED],
            "0",
            id="update",
        ),
        pytest.param(
            TodoServices.REMOVE_ITEM, {ATTR_ITEM: ["Cheese"]}, [], "0", id="remove"
        ),
    ],
)
async def test_update_after_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    service: TodoServices,
    data: dict[str, Any],
    todos_after: list[str],
    expected_state: str,
) -> None:
    """Test the list is read in full after a write the report doesn't show."""
    item = Todo(dav_client, None, TODO_NEEDS_ACTION, calendar, "2")
    item.delete = Mock()
    calendar.search.return_value = [item]
    calendar.get_todo_by_uid = MagicMock(return_value=item)
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    dav_client.put.return_value.status = 204
    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.search.return_value = [
        create_todo(calendar, str(idx), ics) for idx, ics in enumerate(todos_after)
    ]
    await hass.services.async_call(
        TODO_DOMAIN, service, data, target={ATTR_ENTITY_ID: TEST_ENTITY}, blocking=True
    )
    # Wait for the fire-and-forget state refresh
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state

    # The first update starts over with a new token, the second one skips again
    await async_update_entity(hass, TEST_ENTITY)
    reads = calendar.search.call_count
    await async_update_entity(hass, TEST_ENTITY)
    assert calendar.search.call_count == reads


def add_item_from_executor(hass: HomeAssistant) -> None:
    """Add an item from an executor job, as during a running update."""
    asyncio.run_coroutine_threadsafe(
        hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "Cheese"},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        ),
        hass.loop,
    ).result()


async def test_update_after_write_during_report(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
) -> None:
    """Test a write during the sync report is read by the same update."""
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)

    def write_during_report(
        sync_token: str | None, disable_fallback: bool
    ) -> SynchronizableCalendarObjectCollection:
        add_item_from_executor(hass)
        return sync_report("token-1")

    calendar.get_objects_by_sync_token.side_effect = write_during_report
    calendar.search.return_value = [create_todo(calendar, "1", TODO_NEEDS_ACTION)]
    await async_update_entity(hass, TEST_ENTITY)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


async def test_update_after_write_during_read(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
) -> None:
    """Test a write during a full read is read on the next update."""
    calendar.get_objects_by_sync_token.side_effect = [
        sync_report("token-1"),
        sync_report("token-2"),
        sync_report("token-2"),
    ]
    await hass.config_entries.async_setup(config_entry.entry_id)

    def write_during_search(**kwargs: Any) -> list[Todo]:
        add_item_from_executor(hass)
        return []

    calendar.search.side_effect = write_during_search
    await async_update_entity(hass, TEST_ENTITY)

    calendar.search.side_effect = None
    calendar.search.return_value = [create_todo(calendar, "1", TODO_NEEDS_ACTION)]
    await async_update_entity(hass, TEST_ENTITY)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"
    calendar.get_objects_by_sync_token.assert_called_with(
        "token-2", disable_fallback=True
    )


async def test_update_after_partial_delete(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
) -> None:
    """Test the list is read in full after a delete that failed halfway."""
    item1 = Todo(dav_client, None, TODO_NEEDS_ACTION, calendar, "2")
    item2 = Todo(dav_client, None, TODO_NO_STATUS, calendar, "1")
    item1.delete = Mock()
    item2.delete = Mock(side_effect=DAVError)
    calendar.search.return_value = [item1, item2]
    calendar.get_todo_by_uid = Mock(side_effect={"2": item1, "1": item2}.get)
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.search.return_value = [item2]
    with pytest.raises(HomeAssistantError, match="CalDAV delete error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: ["Cheese", "Milk"]},
            target={ATTR_ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    await async_update_entity(hass, TEST_ENTITY)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"
