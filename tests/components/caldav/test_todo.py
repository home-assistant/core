"""The tests for the webdav todo component."""

import asyncio
from datetime import UTC, date, datetime
import threading
import time
from typing import Any, Literal
from unittest.mock import MagicMock, Mock

from caldav.calendarobjectresource import Todo
from caldav.collection import SynchronizableCalendarObjectCollection
from caldav.elements import cdav, dav
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
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import async_update_entity

CALENDAR_NAME = "My Tasks"
ENTITY_NAME = "My tasks"
TEST_ENTITY = "todo.my_tasks"
SUPPORTED_FEATURES = 127

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


TODO_OVERRIDE_FIRST = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:b
RECURRENCE-ID:20010108T090000Z
SUMMARY:b
END:VTODO
BEGIN:VTODO
UID:b
DTSTART:20010101T090000Z
RRULE:FREQ=WEEKLY
SUMMARY:b
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
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
@pytest.mark.freeze_time("2023-11-25 12:00:00+00:00")
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
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )
    # Wait for the fire-and-forget state refresh
    await hass.async_block_till_done()

    assert calendar.add_todo.call_args
    assert calendar.add_todo.call_args.kwargs == {
        "created": datetime(2023, 11, 25, 12, tzinfo=UTC),
        **expcted_save_args,
    }
    assert calendar.add_todo.call_args.kwargs["created"].tzinfo is UTC

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
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("side_effect", "match"),
    [(DAVError, "CalDAV lookup error"), (NotFoundError, "changed on the server")],
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
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    assert item1.delete.called == expect_item1_delete_called
    assert item2.delete.called == expect_item2_delete_called


@pytest.mark.parametrize(
    ("todos", "side_effect", "match"),
    [
        ([TODO_NEEDS_ACTION], DAVError, "CalDAV lookup error"),
        ([TODO_NEEDS_ACTION], NotFoundError, "changed on the server"),
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
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
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

    with pytest.raises(HomeAssistantError, match="changed on the server"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: "Cheese"},
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
        TODO_DOMAIN,
        service,
        data,
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
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
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
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
    """Test a write during a full read is read right after it."""
    calendar.get_objects_by_sync_token.side_effect = [
        sync_report("token-1"),
        sync_report("token-2"),
        sync_report("token-2"),
    ]
    await hass.config_entries.async_setup(config_entry.entry_id)

    def write_during_search(**kwargs: Any) -> list[Todo]:
        add_item_from_executor(hass)
        calendar.search.side_effect = None
        calendar.search.return_value = [create_todo(calendar, "1", TODO_NEEDS_ACTION)]
        return []

    calendar.search.side_effect = write_during_search
    await async_update_entity(hass, TEST_ENTITY)
    await hass.async_block_till_done()

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
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    await async_update_entity(hass, TEST_ENTITY)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


def sorted_todo(uid: str, *lines: str) -> str:
    """Return a VTODO with the given uid as its summary and extra lines."""
    return "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//E-Corp.//CalDAV Client//EN",
            "BEGIN:VTODO",
            f"UID:{uid}",
            f"SUMMARY:{uid}",
            *lines,
            "END:VTODO",
            "END:VCALENDAR",
        ]
    )


@pytest.mark.parametrize(
    ("items", "expected_order"),
    [
        pytest.param(
            [
                sorted_todo("c", "X-APPLE-SORT-ORDER:30"),
                sorted_todo("a", "X-APPLE-SORT-ORDER:-10"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:020"),
            ],
            ["a", "b", "c"],
            id="sort_order",
        ),
        pytest.param(
            [
                sorted_todo("c", "CREATED:20010102T000000Z"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("a"),
            ],
            ["a", "b", "c"],
            id="creation_time",
        ),
        pytest.param(
            [
                sorted_todo("b", "X-APPLE-SORT-ORDER:150"),
                sorted_todo("a", "CREATED:20010101T000140"),
            ],
            ["a", "b"],
            id="creation_time_without_time_zone",
        ),
        pytest.param(
            [
                sorted_todo("b", "CREATED:99991231T235959"),
                sorted_todo("a", "X-APPLE-SORT-ORDER:0"),
            ],
            ["a", "b"],
            id="last_creation_time_without_time_zone",
        ),
        pytest.param(
            [
                sorted_todo("c", "X-APPLE-SORT-ORDER:1.5", "CREATED:20010101T000300Z"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:next", "CREATED:20010101T000200Z"),
                sorted_todo("a", "CREATED:20010101T000100Z"),
            ],
            ["a", "b", "c"],
            id="not_a_whole_number",
        ),
        pytest.param(
            [
                sorted_todo("b", "X-APPLE-SORT-ORDER:10"),
                sorted_todo("a", "X-APPLE-SORT-ORDER:10"),
            ],
            ["b", "a"],
            id="same_position",
        ),
    ],
)
async def test_todo_list_order(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    items: list[str],
    expected_order: list[str],
) -> None:
    """Test the items are listed by their sort order, or else their creation time."""
    calendar.search.return_value = [
        Todo(dav_client, None, item, calendar) for item in items
    ]
    await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
        return_response=True,
    )
    assert [item["uid"] for item in result[TEST_ENTITY]["items"]] == expected_order


def saved_positions(dav_client: Mock) -> list[tuple[str, str | None]]:
    """Return the uid and sort order of each saved item."""
    saved = []
    for call in dav_client.put.call_args_list:
        lines = call.args[1].splitlines()
        uid = next(
            line.removeprefix("UID:") for line in lines if line.startswith("UID:")
        )
        position = next(
            (
                line.removeprefix("X-APPLE-SORT-ORDER:")
                for line in lines
                if line.startswith("X-APPLE-SORT-ORDER:")
            ),
            None,
        )
        saved.append((uid, position))
    return saved


@pytest.mark.parametrize(
    ("server_todos", "move", "expected_saved", "expected_order"),
    [
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:300"),
            ],
            {"uid": "c", "previous_uid": "a"},
            [("c", "150")],
            ["a", "c", "b"],
            id="up",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:300"),
            ],
            {"uid": "a", "previous_uid": "b"},
            [("a", "250")],
            ["b", "a", "c"],
            id="down",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:0"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:10000"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:20000"),
            ],
            {"uid": "c", "previous_uid": "a"},
            [("c", "1024")],
            ["a", "c", "b"],
            id="large_gap",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:300"),
            ],
            {"uid": "c"},
            [("c", "-924")],
            ["c", "a", "b"],
            id="to_top",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
            ],
            {"uid": "a", "previous_uid": "b"},
            [("a", "1224")],
            ["b", "a"],
            id="to_bottom",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:3500"),
            ],
            {"uid": "a", "previous_uid": "b"},
            [("a", "3550")],
            ["b", "a"],
            id="to_bottom_before_now",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:5000"),
            ],
            {"uid": "a", "previous_uid": "b"},
            [("a", "5001")],
            ["b", "a"],
            id="to_bottom_after_now",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:101"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:101"),
                sorted_todo("d", "X-APPLE-SORT-ORDER:200"),
                sorted_todo("e", "X-APPLE-SORT-ORDER:300"),
                sorted_todo("f", "X-APPLE-SORT-ORDER:10000"),
            ],
            {"uid": "e", "previous_uid": "a"},
            [("c", "175"), ("b", "150"), ("e", "125")],
            ["a", "e", "b", "c", "d", "f"],
            id="no_room",
        ),
        pytest.param(
            [sorted_todo("a"), sorted_todo("b"), sorted_todo("c")],
            {"uid": "c", "previous_uid": "a"},
            [("b", "2048"), ("c", "1024")],
            ["a", "c", "b"],
            id="no_positions",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:100"),
            ],
            {"uid": "c", "previous_uid": "a"},
            [("c", "150")],
            ["a", "c", "b"],
            id="same_position_as_previous",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:200"),
            ],
            {"uid": "b", "previous_uid": "a"},
            [("b", "150")],
            ["a", "b", "c"],
            id="same_position_as_next",
        ),
        pytest.param(
            [
                sorted_todo("a", "CREATED:20010101T000140Z"),
                sorted_todo("b", "CREATED:20010101T000320Z"),
            ],
            {"uid": "b"},
            [("b", "-924")],
            ["b", "a"],
            id="creation_time",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("x", "X-APPLE-SORT-ORDER:101", "STATUS:COMPLETED"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:102"),
                sorted_todo("c", "X-APPLE-SORT-ORDER:300"),
            ],
            {"uid": "c", "previous_uid": "a"},
            [("c", "101")],
            ["a", "c", "b"],
            id="completed_apart",
        ),
        pytest.param(
            [
                sorted_todo("x", "X-APPLE-SORT-ORDER:50", "STATUS:COMPLETED"),
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
            ],
            {"uid": "a"},
            [],
            ["a"],
            id="only_open_item",
        ),
        pytest.param(
            [
                sorted_todo("x", "X-APPLE-SORT-ORDER:100", "STATUS:COMPLETED"),
                sorted_todo("a", "X-APPLE-SORT-ORDER:150"),
                sorted_todo("y", "X-APPLE-SORT-ORDER:200", "STATUS:COMPLETED"),
            ],
            {"uid": "y"},
            [("y", "-924")],
            ["a"],
            id="completed_item",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
            ],
            {"uid": "b", "previous_uid": "a"},
            [],
            ["a", "b"],
            id="same_place",
        ),
        pytest.param(
            [
                sorted_todo("a", "X-APPLE-SORT-ORDER:100"),
                sorted_todo("b", "X-APPLE-SORT-ORDER:200"),
            ],
            {"uid": "a"},
            [],
            ["a", "b"],
            id="already_on_top",
        ),
        pytest.param(
            [sorted_todo("a", "X-APPLE-SORT-ORDER:100")],
            {"uid": "a", "previous_uid": "a"},
            [],
            ["a"],
            id="behind_itself",
        ),
    ],
)
@pytest.mark.freeze_time("2001-01-01 01:00:00+00:00")
async def test_move_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
    server_todos: list[str],
    move: dict[str, str],
    expected_saved: list[tuple[str, str]],
    expected_order: list[str],
) -> None:
    """Test moving an item saves the positions it needs."""
    calendar.search.return_value = [
        Todo(dav_client, None, todo, calendar) for todo in server_todos
    ]
    dav_client.put.return_value.status = 204
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, **move}
    )
    resp = await client.receive_json()
    assert resp["success"]
    await hass.async_block_till_done()

    assert saved_positions(dav_client) == expected_saved
    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {"status": ["needs_action"]},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
        return_response=True,
    )
    assert [item["uid"] for item in result[TEST_ENTITY]["items"]] == expected_order


async def test_move_item_keeps_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a new position keeps what vobject drops from the item."""
    calendar.search.side_effect = lambda **kwargs: [
        Todo(dav_client, None, sorted_todo("a"), calendar),
        Todo(
            dav_client,
            None,
            sorted_todo(
                "b",
                "SEQUENCE:3",
                "X-APPLE-STRUCTURED-LOCATION;VALUE=URI:geo:52.5,13.4",
            ),
            calendar,
        ),
    ]
    dav_client.put.return_value.status = 204
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    lines = dav_client.put.call_args.args[1].splitlines()
    assert "SEQUENCE:3" in lines
    assert any(line.endswith("13.4") for line in lines)


@pytest.mark.freeze_time("2001-01-01 01:00:00+00:00")
async def test_move_item_saves_resource_as_read(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a todo stored with a changed occurrence first is saved as it is."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo("a", "X-APPLE-SORT-ORDER:100"), calendar),
        Todo(
            dav_client,
            None,
            TODO_OVERRIDE_FIRST,
            calendar,
        ),
    ]
    dav_client.put.return_value.status = 204
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": "b",
            "previous_uid": "a",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    lines = dav_client.put.call_args.args[1].splitlines()
    assert lines.index("X-APPLE-SORT-ORDER:1124") < lines.index("RRULE:FREQ=WEEKLY")
    assert not calendar.get_todo_by_uid.called


async def test_move_items_one_after_another(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a second move reads the list after the first one saved."""
    events: list[str] = []
    todos = [Todo(dav_client, None, sorted_todo(uid), calendar) for uid in "abc"]

    def search(**kwargs: Any) -> list[Todo]:
        events.append("read")
        return todos

    def put(*args: Any) -> MagicMock:
        time.sleep(0.05)
        events.append("save")
        return MagicMock(status=204)

    calendar.search.side_effect = search
    dav_client.put.side_effect = put
    await hass.config_entries.async_setup(config_entry.entry_id)
    events.clear()

    client = await hass_ws_client(hass)
    for uid in ("c", "b"):
        await client.send_json_auto_id(
            {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": uid}
        )
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()

    assert events.index("save") < events.index("read", 1)


async def test_move_item_in_place(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a move that changes nothing doesn't read the list again."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo("a", "X-APPLE-SORT-ORDER:1"), calendar),
        Todo(dav_client, None, sorted_todo("b", "X-APPLE-SORT-ORDER:2"), calendar),
    ]
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)
    reads = calendar.search.call_count

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "a"}
    )
    resp = await client.receive_json()
    assert resp["success"]
    await hass.async_block_till_done()

    assert calendar.search.call_count == reads + 1


@pytest.mark.parametrize(
    "sync_token", ["token-2", "token-1"], ids=["report_changed", "report_missed"]
)
async def test_move_item_in_place_refreshes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
    sync_token: str,
) -> None:
    """Test a move that saves nothing still shows the order the server has."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo("a", "X-APPLE-SORT-ORDER:1"), calendar),
        Todo(dav_client, None, sorted_todo("b", "X-APPLE-SORT-ORDER:2"), calendar),
    ]
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)
    subscriber = await hass_ws_client(hass)
    await subscriber.send_json_auto_id(
        {"type": "todo/item/subscribe", "entity_id": TEST_ENTITY}
    )
    assert (await subscriber.receive_json())["success"]
    msg = await subscriber.receive_json()
    assert [item["uid"] for item in msg["event"]["items"]] == ["a", "b"]
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo("a", "X-APPLE-SORT-ORDER:2"), calendar),
        Todo(dav_client, None, sorted_todo("b", "X-APPLE-SORT-ORDER:1"), calendar),
    ]
    calendar.get_objects_by_sync_token.return_value = sync_report(sync_token)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
    )
    resp = await client.receive_json()
    assert resp["success"]
    await hass.async_block_till_done()

    assert not dav_client.put.called
    msg = await subscriber.receive_json()
    assert [item["uid"] for item in msg["event"]["items"]] == ["b", "a"]


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (TodoServices.UPDATE_ITEM, {ATTR_ITEM: "b", ATTR_STATUS: "completed"}),
        (TodoServices.REMOVE_ITEM, {ATTR_ITEM: ["b"]}),
    ],
    ids=["update", "remove"],
)
async def test_write_waits_for_move(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    service: TodoServices,
    data: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a write during a move waits until the move has saved."""
    events: list[str] = []
    todos = [Todo(dav_client, None, sorted_todo(uid), calendar) for uid in "abc"]
    for todo in todos:
        todo.delete = Mock()

    def lookup(uid: str) -> Todo:
        events.append("lookup")
        return next(todo for todo in todos if todo.id == uid)

    async def start_write() -> None:
        hass.async_create_task(
            hass.services.async_call(
                TODO_DOMAIN,
                service,
                data,
                target={TargetKey.ENTITY_ID: TEST_ENTITY},
                blocking=True,
            )
        )

    def put(*args: Any) -> MagicMock:
        if not events:
            asyncio.run_coroutine_threadsafe(start_write(), hass.loop).result()
        events.append("save")
        return MagicMock(status=204)

    calendar.search.return_value = todos
    calendar.get_todo_by_uid = Mock(side_effect=lookup)
    dav_client.put.side_effect = put
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": "c",
            "previous_uid": "a",
        }
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()

    assert events[:3] == ["save", "save", "lookup"]


async def test_update_after_move(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the list is read in full after a move the report doesn't show."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo("a", "X-APPLE-SORT-ORDER:1"), calendar),
        Todo(dav_client, None, sorted_todo("b", "X-APPLE-SORT-ORDER:2"), calendar),
    ]
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    dav_client.put.return_value.status = 204
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
    )
    resp = await client.receive_json()
    assert resp["success"]
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
        return_response=True,
    )
    assert [item["uid"] for item in result[TEST_ENTITY]["items"]] == ["b", "a"]


@pytest.mark.parametrize(
    "put_result",
    [
        pytest.param([MagicMock(status=204), DAVError()], id="second_save_fails"),
        pytest.param(caldav_requests.exceptions.Timeout(), id="first_save_times_out"),
    ],
)
async def test_update_after_failed_move(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
    put_result: list[Any] | Exception,
) -> None:
    """Test the list is read in full after a move whose saves failed."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo(uid), calendar) for uid in ("a", "b", "c")
    ]
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    dav_client.put.side_effect = put_result
    await hass.config_entries.async_setup(config_entry.entry_id)
    reads = calendar.search.call_count

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": "c",
            "previous_uid": "a",
        }
    )
    resp = await client.receive_json()
    assert resp["error"]["message"].startswith("CalDAV save error")
    await hass.async_block_till_done()

    assert calendar.search.call_count == reads + 2


async def test_move_item_removed_elsewhere(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a move of an item removed elsewhere shows the list without it."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo(uid), calendar) for uid in ("a", "b")
    ]
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)
    calendar.search.return_value = [Todo(dav_client, None, sorted_todo("a"), calendar)]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
    )
    resp = await client.receive_json()
    assert resp["error"]["message"] == "Could not find To-do item b"
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "1"


@pytest.mark.parametrize(
    "move",
    [{"uid": "unknown"}, {"uid": "a", "previous_uid": "unknown"}],
    ids=["unknown_item", "unknown_previous_item"],
)
async def test_move_item_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
    move: dict[str, str],
) -> None:
    """Test moving an item that is not on the list."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo("a"), calendar),
    ]
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, **move}
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"] == {
        "code": "failed",
        "message": "Could not find To-do item unknown",
    }
    assert not dav_client.put.called


@pytest.mark.parametrize(
    "error",
    [
        DAVError(),
        caldav_requests.exceptions.ConnectionError(),
        caldav_requests.exceptions.Timeout(),
    ],
    ids=["dav_error", "connection_error", "timeout"],
)
async def test_move_item_lookup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
    error: Exception,
) -> None:
    """Test failure reading the list to move an item."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    calendar.search.side_effect = error

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "a"}
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "failed"
    assert resp["error"]["message"].startswith("CalDAV lookup error")


@pytest.mark.parametrize(
    "error",
    [
        DAVError(),
        caldav_requests.exceptions.ConnectionError(),
        caldav_requests.exceptions.Timeout(),
    ],
    ids=["dav_error", "connection_error", "timeout"],
)
async def test_move_item_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
    error: Exception,
) -> None:
    """Test failure saving the new position of an item."""
    calendar.search.return_value = [
        Todo(dav_client, None, sorted_todo("a", "X-APPLE-SORT-ORDER:1"), calendar),
        Todo(dav_client, None, sorted_todo("b", "X-APPLE-SORT-ORDER:2"), calendar),
    ]
    dav_client.put.side_effect = error
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "failed"
    assert resp["error"]["message"].startswith("CalDAV save error")


async def test_move_item_past_unreadable_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a move fails cleanly on an item whose position cannot be written."""
    calendar.search.side_effect = lambda **kwargs: [
        Todo(dav_client, None, sorted_todo("a"), calendar),
        Todo(dav_client, None, sorted_todo("b", "PRIORITY:high"), calendar),
        Todo(dav_client, None, sorted_todo("c"), calendar),
    ]
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": "c",
            "previous_uid": "a",
        }
    )
    resp = await client.receive_json()
    assert resp["error"]["code"] == "failed"
    assert resp["error"]["message"].startswith("CalDAV lookup error")
    assert not dav_client.put.called


class FakeServer:
    """A calendar that gives each stored todo a new ETag and honors If-Match."""

    def __init__(self, dav_client: Mock, calendar: Mock) -> None:
        """Answer the reads and writes of the calendar."""
        self.todos: dict[str, str] = {}
        self.etags: dict[str, str] = {}
        self.schedule_tags = False
        self.fixed_schedule_tag: str | None = None
        self.put_etag: Literal["strong", "weak"] | None = "strong"
        self._dav_client = dav_client
        self._calendar = calendar
        self._versions = 0
        calendar.search.side_effect = self.search
        calendar.get_todo_by_uid.side_effect = self.lookup
        dav_client.put.side_effect = self.put
        dav_client.delete.side_effect = self.delete

    def store(self, uid: str, *lines: str, etag: str | None = None) -> None:
        """Store a todo with the given lines, as another client does."""
        self.store_ics(uid, sorted_todo(uid, *lines), etag)

    def store_ics(self, uid: str, ics: str, etag: str | None = None) -> None:
        """Store a todo, as another client does."""
        self._versions += 1
        self.todos[uid] = ics
        self.etags[uid] = etag or f'"{self._versions}"'

    def url(self, uid: str) -> str:
        """Return the URL of a todo."""
        return str(self._dav_client.url.join(f"{uid}.ics"))

    def schedule_tag(self, uid: str) -> str:
        """Return the Schedule-Tag of a todo, unless fixed one for each version."""
        return self.fixed_schedule_tag or f'"s{self.etags[uid].strip('"')}"'

    def lookup(self, uid: str, with_etag: bool = True) -> Todo:
        """Return a todo, with its ETag as a report has it."""
        if uid not in self.todos:
            raise NotFoundError
        props = {dav.GetEtag.tag: self.etags[uid]} if with_etag else {}
        if self.schedule_tags:
            props[cdav.ScheduleTag.tag] = self.schedule_tag(uid)
        return Todo(
            self._dav_client, f"{uid}.ics", self.todos[uid], self._calendar, uid, props
        )

    def search(self, **kwargs: Any) -> list[Todo]:
        """Return all todos with their ETags."""
        return [self.lookup(uid) for uid in self.todos]

    def _refuses(self, uid: str, headers: dict[str, str]) -> bool:
        return headers.get("if-match") not in (None, "*", self.etags[uid]) or (
            headers.get("if-schedule-tag-match") not in (None, self.schedule_tag(uid))
        )

    def put(self, url: str, data: str, headers: dict[str, str]) -> MagicMock:
        """Store a todo unless another version than the stored one is expected."""
        uid = url.rsplit("/", 1)[-1].removesuffix(".ics")
        if self._refuses(uid, headers):
            return MagicMock(status=412)
        self._versions += 1
        self.todos[uid] = data
        self.etags[uid] = f'"{self._versions}"'
        headers = {}
        if self.put_etag is not None:
            weak = "W/" if self.put_etag == "weak" else ""
            headers["Etag"] = weak + self.etags[uid]
        return MagicMock(status=204, headers=headers)

    def delete(self, url: str, headers: dict[str, str] | None = None) -> MagicMock:
        """Delete a todo unless another version than the stored one is expected."""
        uid = url.rsplit("/", 1)[-1].removesuffix(".ics")
        if uid not in self.todos:
            return MagicMock(status=404)
        if self._refuses(uid, headers or {}):
            return MagicMock(status=412)
        del self.todos[uid]
        return MagicMock(status=204)


@pytest.fixture(name="server")
def mock_server(dav_client: Mock, calendar: Mock) -> FakeServer:
    """Fixture for a calendar that honors If-Match."""
    return FakeServer(dav_client, calendar)


async def get_items(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return the items the list shows."""
    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
        return_response=True,
    )
    return result[TEST_ENTITY]["items"]


ITEM_CHANGED = (
    "The to-do item was changed on the server in the meantime. "
    "Check the list and try again"
)
CHANGED_ELSEWHERE = {
    "uid": "a",
    "summary": "a",
    "status": "needs_action",
    "description": "Added elsewhere",
}


@pytest.mark.parametrize(
    ("data", "lookup_with_etag"),
    [
        ({ATTR_RENAME: "b"}, True),
        ({ATTR_STATUS: "completed"}, True),
        ({ATTR_STATUS: "completed"}, False),
    ],
    ids=["rename", "complete", "complete_found_without_etag"],
)
async def test_update_item_changed_elsewhere(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    data: dict[str, Any],
    lookup_with_etag: bool,
) -> None:
    """Test an update doesn't overwrite an item changed since the list was read."""
    server.store("a")
    calendar.get_todo_by_uid.side_effect = lambda uid: server.lookup(
        uid, lookup_with_etag
    )
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)
    server.store("a", "DESCRIPTION:Added elsewhere")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "a", **data},
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "item_changed"
    assert str(err.value) == ITEM_CHANGED
    assert "DESCRIPTION:Added elsewhere" in server.todos["a"]
    assert await get_items(hass) == [CHANGED_ELSEWHERE]


async def test_update_item_found_without_etag_expects_listed_version(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test an item caldav finds without its ETag is saved as the version listed."""
    server.store("a")
    calendar.get_todo_by_uid.side_effect = lambda uid: server.lookup(uid, False)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "a", ATTR_STATUS: "completed"},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    assert dav_client.put.call_args.args[2]["if-match"] == '"1"'
    assert "STATUS:COMPLETED" in server.todos["a"].splitlines()


async def test_update_item_changed_elsewhere_with_changed_occurrence_first(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    server: FakeServer,
) -> None:
    """Test a todo that caldav reads again to save it is not overwritten either."""
    server.store_ics("b", TODO_OVERRIDE_FIRST)
    await hass.config_entries.async_setup(config_entry.entry_id)
    changed = TODO_OVERRIDE_FIRST.replace("SUMMARY:b", "SUMMARY:Changed elsewhere")
    server.store_ics("b", changed)

    with pytest.raises(HomeAssistantError, match=ITEM_CHANGED):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "b", ATTR_STATUS: "completed"},
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )

    assert server.todos["b"] == changed


async def test_update_skips_unchanged_list_again_after_item_changed_elsewhere(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test a refused write is followed by one full read and a new sync token."""
    server.store("a")
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)
    server.store("a", "DESCRIPTION:Added elsewhere")
    reads = calendar.search.call_count

    with pytest.raises(HomeAssistantError, match=ITEM_CHANGED):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "a", ATTR_STATUS: "completed"},
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert calendar.search.call_count == reads + 1

    await async_update_entity(hass, TEST_ENTITY)
    calendar.get_objects_by_sync_token.assert_called_with(None, disable_fallback=True)
    assert calendar.search.call_count == reads + 2
    await async_update_entity(hass, TEST_ENTITY)
    assert calendar.search.call_count == reads + 2


@pytest.mark.parametrize(
    ("lookup_with_etag", "expected_left"),
    [(True, ["b", "a", "c"]), (False, ["a", "c"])],
    ids=["found_with_etag", "found_without_etag"],
)
async def test_remove_items_changed_elsewhere(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    lookup_with_etag: bool,
    expected_left: list[str],
) -> None:
    """Test a delete doesn't remove an item changed since the list was read."""
    server.store("b")
    server.store("a")
    server.store("c")
    calendar.get_todo_by_uid.side_effect = lambda uid: server.lookup(
        uid, lookup_with_etag
    )
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)
    server.store("a", "DESCRIPTION:Added elsewhere")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: ["b", "a", "c"]},
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "item_changed"
    assert list(server.todos) == expected_left
    assert "DESCRIPTION:Added elsewhere" in server.todos["a"]
    assert [item["uid"] for item in await get_items(hass)] == expected_left
    assert CHANGED_ELSEWHERE in await get_items(hass)


async def test_remove_item_expects_only_a_strong_etag(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    server: FakeServer,
) -> None:
    """Test a delete expects the listed version unless its ETag is a weak one."""
    server.store("a")
    server.store("b", etag='W/"2"')
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: ["a", "b"]},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )

    assert [request.args for request in dav_client.delete.call_args_list] == [
        (server.url("a"), {"if-match": '"1"'}),
        (server.url("b"),),
    ]


async def test_remove_item_removed_elsewhere_during_delete(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test a delete of an item that is gone by then shows the list without it."""
    server.store("a")
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)

    def remove_after_lookup(uid: str) -> Todo:
        todo = server.lookup(uid)
        del server.todos[uid]
        return todo

    calendar.get_todo_by_uid.side_effect = remove_after_lookup

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: ["a"]},
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "item_changed"
    assert await get_items(hass) == []


async def test_move_item_changed_elsewhere_keeps_that_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a move of an item changed since the list was read keeps that change."""
    server.store("a", "X-APPLE-SORT-ORDER:100")
    server.store("b", "X-APPLE-SORT-ORDER:200")
    server.store("c", "X-APPLE-SORT-ORDER:300")
    await hass.config_entries.async_setup(config_entry.entry_id)
    server.store("c", "X-APPLE-SORT-ORDER:300", "DESCRIPTION:Added elsewhere")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": "c",
            "previous_uid": "a",
        }
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()

    lines = server.todos["c"].splitlines()
    assert "DESCRIPTION:Added elsewhere" in lines
    assert "X-APPLE-SORT-ORDER:150" in lines
    assert await get_items(hass) == [
        {"uid": "a", "summary": "a", "status": "needs_action"},
        {**CHANGED_ELSEWHERE, "uid": "c", "summary": "c"},
        {"uid": "b", "summary": "b", "status": "needs_action"},
    ]


async def update_description(hass: HomeAssistant, description: str) -> None:
    """Change the description of the item b."""
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "b", ATTR_DESCRIPTION: description},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )


@pytest.mark.parametrize(
    "put_etag",
    ["strong", "weak", None],
    ids=["etag_returned", "weak_etag_returned", "no_etag_returned"],
)
@pytest.mark.parametrize("first_write", ["update", "move"])
async def test_update_item_changed_elsewhere_after_own_writes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    hass_ws_client: WebSocketGenerator,
    first_write: str,
    put_etag: Literal["strong", "weak"] | None,
) -> None:
    """Test an item counts as changed by another client only, also before a refresh."""
    server.put_etag = put_etag
    server.store("a", "X-APPLE-SORT-ORDER:100")
    server.store("b", "X-APPLE-SORT-ORDER:200")
    await hass.config_entries.async_setup(config_entry.entry_id)

    if first_write == "update":
        calendar.search.side_effect = DAVError
        await update_description(hass, "First")
    else:
        calendar.search.side_effect = [server.search(), DAVError()]
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
        )
        assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    calendar.search.side_effect = server.search

    await update_description(hass, "Second")
    await hass.async_block_till_done()
    assert "DESCRIPTION:Second" in server.todos["b"].splitlines()

    server.store("b", "DESCRIPTION:Added elsewhere")
    with pytest.raises(HomeAssistantError) as err:
        await update_description(hass, "Third")
    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["b"]


async def test_update_item_changed_elsewhere_after_own_write_during_read(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test a read that an own write overtook doesn't make the item count as changed."""
    server.store("b")
    await hass.config_entries.async_setup(config_entry.entry_id)

    def write_during_search(**kwargs: Any) -> list[Todo]:
        todos = server.search()
        calendar.search.side_effect = DAVError
        asyncio.run_coroutine_threadsafe(
            update_description(hass, "First"), hass.loop
        ).result()
        return todos

    calendar.search.side_effect = write_during_search
    await async_update_entity(hass, TEST_ENTITY)
    await hass.async_block_till_done()
    calendar.search.side_effect = server.search

    await update_description(hass, "Second")
    await hass.async_block_till_done()
    assert "DESCRIPTION:Second" in server.todos["b"].splitlines()

    server.store("b", "DESCRIPTION:Added elsewhere")
    with pytest.raises(HomeAssistantError) as err:
        await update_description(hass, "Third")
    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["b"]


async def update_item(hass: HomeAssistant, item: str, **data: Any) -> None:
    """Update an item of the list."""
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: item, **data},
        target={TargetKey.ENTITY_ID: TEST_ENTITY},
        blocking=True,
    )


async def test_update_item_changed_elsewhere_and_read_during_lookup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test a refresh during the lookup doesn't let the outdated item through."""
    server.store("a")
    await hass.config_entries.async_setup(config_entry.entry_id)
    server.store("a", "DESCRIPTION:Added elsewhere")

    lookup = calendar.get_todo_by_uid

    def refresh_during_lookup(uid: str) -> Todo:
        calendar.get_todo_by_uid = lookup
        asyncio.run_coroutine_threadsafe(
            async_update_entity(hass, TEST_ENTITY), hass.loop
        ).result()
        return server.lookup(uid)

    # A plain function, as the test harness runs a Mock in the event loop
    calendar.get_todo_by_uid = refresh_during_lookup
    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "a", **{ATTR_STATUS: "completed"})

    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["a"]


async def test_update_item_changed_elsewhere_after_lookup_with_occurrence_first(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test a todo with an occurrence first is saved as the version looked up."""
    server.store_ics("b", TODO_OVERRIDE_FIRST)
    await hass.config_entries.async_setup(config_entry.entry_id)
    changed = TODO_OVERRIDE_FIRST.replace("SUMMARY:b", "SUMMARY:Changed elsewhere")

    def change_after_lookup(uid: str) -> Todo:
        todo = server.lookup(uid)
        calendar.get_todo_by_uid.side_effect = server.lookup
        server.store_ics("b", changed)
        return todo

    calendar.get_todo_by_uid.side_effect = change_after_lookup
    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "b", **{ATTR_STATUS: "completed"})

    assert err.value.translation_key == "item_changed"
    assert server.todos["b"] == changed


async def test_update_item_after_own_save_timed_out(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    server: FakeServer,
) -> None:
    """Test a save that timed out but was stored doesn't refuse the next one."""
    server.store("a")
    await hass.config_entries.async_setup(config_entry.entry_id)

    def store_then_time_out(url: str, data: str, headers: dict[str, str]) -> None:
        server.put(url, data, headers)
        raise caldav_requests.exceptions.Timeout

    dav_client.put.side_effect = store_then_time_out
    with pytest.raises(HomeAssistantError, match="CalDAV save error"):
        await update_item(hass, "a", **{ATTR_RENAME: "renamed"})
    await hass.async_block_till_done()
    dav_client.put.side_effect = server.put

    await update_item(hass, "a", **{ATTR_STATUS: "completed"})
    lines = server.todos["a"].splitlines()
    assert "SUMMARY:renamed" in lines
    assert "STATUS:COMPLETED" in lines


@pytest.mark.parametrize(
    "put_etag",
    ["strong", "weak", None],
    ids=["etag_returned", "weak_etag_returned", "no_etag_returned"],
)
async def test_update_item_twice_before_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    put_etag: Literal["strong", "weak"] | None,
) -> None:
    """Test a second update before the list is read again keeps the first one."""
    server.put_etag = put_etag
    server.store("a")
    await hass.config_entries.async_setup(config_entry.entry_id)
    calendar.search.side_effect = DAVError

    await update_item(hass, "a", **{ATTR_RENAME: "renamed"})
    await hass.async_block_till_done()
    await update_item(hass, "a", **{ATTR_STATUS: "completed"})

    lines = server.todos["a"].splitlines()
    assert "SUMMARY:renamed" in lines
    assert "STATUS:COMPLETED" in lines


async def test_update_item_after_own_write_during_read(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test a read that an own write overtook doesn't undo that write."""
    server.store("a")
    await hass.config_entries.async_setup(config_entry.entry_id)

    def rename_during_search(**kwargs: Any) -> list[Todo]:
        todos = server.search()
        calendar.search.side_effect = DAVError
        asyncio.run_coroutine_threadsafe(
            update_item(hass, "a", **{ATTR_RENAME: "renamed"}), hass.loop
        ).result()
        return todos

    calendar.search.side_effect = rename_during_search
    await async_update_entity(hass, TEST_ENTITY)
    await hass.async_block_till_done()
    await update_item(hass, "a", **{ATTR_STATUS: "completed"})

    lines = server.todos["a"].splitlines()
    assert "SUMMARY:renamed" in lines
    assert "STATUS:COMPLETED" in lines


@pytest.mark.parametrize("first_write", ["update", "move"])
async def test_update_other_item_changed_elsewhere_after_own_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    hass_ws_client: WebSocketGenerator,
    first_write: str,
) -> None:
    """Test an own write keeps the check of the other items until the next read."""
    server.store("a", "X-APPLE-SORT-ORDER:100")
    server.store("b", "X-APPLE-SORT-ORDER:200")
    await hass.config_entries.async_setup(config_entry.entry_id)

    if first_write == "update":
        calendar.search.side_effect = DAVError
        await update_description(hass, "Own")
    else:
        calendar.search.side_effect = [server.search(), DAVError()]
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
        )
        assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    calendar.search.side_effect = server.search
    server.store("a", "X-APPLE-SORT-ORDER:100", "DESCRIPTION:Added elsewhere")

    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "a", **{ATTR_STATUS: "completed"})
    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["a"]


@pytest.mark.parametrize("first_write", ["update", "move"])
async def test_update_item_changed_elsewhere_after_own_write_before_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    hass_ws_client: WebSocketGenerator,
    first_write: str,
) -> None:
    """Test an item changed after an own write is refused before the list is read."""
    server.store("a", "X-APPLE-SORT-ORDER:100")
    server.store("b", "X-APPLE-SORT-ORDER:200")
    await hass.config_entries.async_setup(config_entry.entry_id)

    if first_write == "update":
        calendar.search.side_effect = DAVError
        await update_description(hass, "Own")
    else:
        calendar.search.side_effect = [server.search(), DAVError()]
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
        )
        assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    calendar.search.side_effect = DAVError
    server.store("b", "DESCRIPTION:Added elsewhere")

    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "b", **{ATTR_STATUS: "completed"})
    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["b"]


async def test_update_item_moved_after_it_changed_elsewhere(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a move of an item changed elsewhere doesn't make that change count as shown."""
    server.store("a", "X-APPLE-SORT-ORDER:100")
    server.store("b", "X-APPLE-SORT-ORDER:200")
    await hass.config_entries.async_setup(config_entry.entry_id)
    server.store("b", "X-APPLE-SORT-ORDER:200", "DESCRIPTION:Added elsewhere")

    calendar.search.side_effect = [server.search(), DAVError()]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "todo/item/move", "entity_id": TEST_ENTITY, "uid": "b"}
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    calendar.search.side_effect = DAVError

    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "b", **{ATTR_STATUS: "completed"})
    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["b"]


@pytest.mark.parametrize(
    "changed_elsewhere", [False, True], ids=["unchanged", "changed_elsewhere"]
)
async def test_update_item_spread_out_by_move(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    hass_ws_client: WebSocketGenerator,
    changed_elsewhere: bool,
) -> None:
    """Test an item spread out by a move is checked like the moved one."""
    server.store("a", "X-APPLE-SORT-ORDER:100")
    server.store("b", "X-APPLE-SORT-ORDER:101")
    server.store("c", "X-APPLE-SORT-ORDER:102")
    await hass.config_entries.async_setup(config_entry.entry_id)

    calendar.search.side_effect = [server.search(), DAVError()]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "todo/item/move",
            "entity_id": TEST_ENTITY,
            "uid": "c",
            "previous_uid": "a",
        }
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    assert "X-APPLE-SORT-ORDER:101" not in server.todos["b"]
    calendar.search.side_effect = DAVError
    if changed_elsewhere:
        server.store_ics(
            "b",
            server.todos["b"].replace(
                "END:VTODO", "DESCRIPTION:Added elsewhere\nEND:VTODO"
            ),
        )
        with pytest.raises(HomeAssistantError) as err:
            await update_item(hass, "b", **{ATTR_STATUS: "completed"})
        assert err.value.translation_key == "item_changed"
        assert "DESCRIPTION:Added elsewhere" in server.todos["b"]
    else:
        await update_item(hass, "b", **{ATTR_STATUS: "completed"})
        assert "STATUS:COMPLETED" in server.todos["b"].splitlines()


@pytest.mark.parametrize(
    ("etag", "fixed_schedule_tag"),
    [(None, None), ('W/"1"', None), (None, '"s"')],
    ids=["strong_etag", "weak_etag", "schedule_tag_kept_on_change"],
)
async def test_update_item_changed_elsewhere_after_lookup_with_schedule_tag(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    etag: str | None,
    fixed_schedule_tag: str | None,
) -> None:
    """Test an item with a Schedule-Tag, as Xandikos gives every item, is saved as listed."""
    server.schedule_tags = True
    server.fixed_schedule_tag = fixed_schedule_tag
    server.store("a", etag=etag)
    await hass.config_entries.async_setup(config_entry.entry_id)

    def change_after_lookup(uid: str) -> Todo:
        todo = server.lookup(uid)
        calendar.get_todo_by_uid.side_effect = server.lookup
        server.store("a", "DESCRIPTION:Added elsewhere")
        return todo

    calendar.get_todo_by_uid.side_effect = change_after_lookup
    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "a", **{ATTR_STATUS: "completed"})
    await hass.async_block_till_done()
    assert err.value.translation_key == "item_changed"

    await update_item(hass, "a", **{ATTR_RENAME: "renamed"})
    lines = server.todos["a"].splitlines()
    assert "SUMMARY:renamed" in lines
    assert "DESCRIPTION:Added elsewhere" in lines


@pytest.mark.parametrize("stored", [False, True], ids=["not_stored", "stored"])
async def test_update_item_changed_elsewhere_after_own_save_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    dav_client: Mock,
    server: FakeServer,
    stored: bool,
) -> None:
    """Test an item is still checked after a failed save, also if no read follows."""
    server.store("a")
    await hass.config_entries.async_setup(config_entry.entry_id)
    calendar.search.side_effect = DAVError

    def time_out(url: str, data: str, headers: dict[str, str]) -> None:
        if stored:
            server.put(url, data, headers)
        raise caldav_requests.exceptions.Timeout

    dav_client.put.side_effect = time_out
    with pytest.raises(HomeAssistantError, match="CalDAV save error"):
        await update_item(hass, "a", **{ATTR_RENAME: "renamed"})
    await hass.async_block_till_done()
    dav_client.put.side_effect = server.put
    server.store("a", "DESCRIPTION:Added elsewhere")

    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "a", **{ATTR_STATUS: "completed"})
    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["a"]


async def test_update_item_after_own_save_timed_out_during_read(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    dav_client: Mock,
    server: FakeServer,
) -> None:
    """Test a read that a stored but timed out save overtook doesn't refuse the next one."""
    server.store("a")
    await hass.config_entries.async_setup(config_entry.entry_id)

    def store_then_time_out(url: str, data: str, headers: dict[str, str]) -> None:
        server.put(url, data, headers)
        raise caldav_requests.exceptions.Timeout

    errors: list[HomeAssistantError] = []

    def save_during_search(**kwargs: Any) -> list[Todo]:
        todos = server.search()
        calendar.search.side_effect = server.search
        dav_client.put.side_effect = store_then_time_out
        try:
            asyncio.run_coroutine_threadsafe(
                update_item(hass, "a", **{ATTR_RENAME: "renamed"}), hass.loop
            ).result()
        except HomeAssistantError as err:
            errors.append(err)
        dav_client.put.side_effect = server.put
        return todos

    calendar.search.side_effect = save_during_search
    await async_update_entity(hass, TEST_ENTITY)
    await hass.async_block_till_done()
    assert str(errors[0]).startswith("CalDAV save error")

    await update_item(hass, "a", **{ATTR_STATUS: "completed"})
    lines = server.todos["a"].splitlines()
    assert "SUMMARY:renamed" in lines
    assert "STATUS:COMPLETED" in lines


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (TodoServices.UPDATE_ITEM, {ATTR_ITEM: "a", ATTR_RENAME: "renamed"}),
        (TodoServices.REMOVE_ITEM, {ATTR_ITEM: ["a"]}),
    ],
    ids=["update", "remove"],
)
async def test_write_item_removed_elsewhere(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
    service: TodoServices,
    data: dict[str, Any],
) -> None:
    """Test a write of an item removed since the list was read shows the list without it."""
    server.store("a")
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)
    del server.todos["a"]

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            TODO_DOMAIN,
            service,
            data,
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "item_changed"
    assert await get_items(hass) == []


async def test_update_item_removed_elsewhere_after_lookup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendar: Mock,
    server: FakeServer,
) -> None:
    """Test an update of an item removed after its lookup shows the list without it."""
    server.store("a")
    calendar.get_objects_by_sync_token.return_value = sync_report("token-1")
    await hass.config_entries.async_setup(config_entry.entry_id)

    def remove_after_lookup(uid: str) -> Todo:
        todo = server.lookup(uid)
        calendar.get_todo_by_uid.side_effect = server.lookup
        del server.todos[uid]
        return todo

    calendar.get_todo_by_uid.side_effect = remove_after_lookup
    with pytest.raises(HomeAssistantError) as err:
        await update_item(hass, "a", **{ATTR_RENAME: "renamed"})
    await hass.async_block_till_done()

    assert err.value.translation_key == "item_changed"
    assert server.todos == {}
    assert await get_items(hass) == []


async def test_update_item_again_while_it_is_saved(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    server: FakeServer,
) -> None:
    """Test an update sent while the item is saved doesn't undo that save."""
    server.store("a")
    await hass.config_entries.async_setup(config_entry.entry_id)
    saving, release = threading.Event(), threading.Event()

    def save_on_release(url: str, data: str, headers: dict[str, str]) -> MagicMock:
        dav_client.put.side_effect = server.put
        saving.set()
        release.wait(5)
        return server.put(url, data, headers)

    dav_client.put.side_effect = save_on_release
    rename = hass.async_create_task(update_item(hass, "a", **{ATTR_RENAME: "renamed"}))
    await hass.async_add_executor_job(saving.wait, 5)
    complete = hass.async_create_task(
        update_item(hass, "a", **{ATTR_STATUS: "completed"})
    )
    await asyncio.sleep(0)
    release.set()
    await rename

    with pytest.raises(HomeAssistantError) as err:
        await complete
    assert err.value.translation_key == "item_changed"
    assert "SUMMARY:renamed" in server.todos["a"].splitlines()


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (TodoServices.UPDATE_ITEM, {ATTR_ITEM: "a", ATTR_STATUS: "completed"}),
        (TodoServices.REMOVE_ITEM, {ATTR_ITEM: ["a"]}),
    ],
    ids=["update", "remove"],
)
async def test_write_item_changed_elsewhere_and_read_while_waiting(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    server: FakeServer,
    service: TodoServices,
    data: dict[str, Any],
) -> None:
    """Test a refresh while a write waits for another doesn't let the outdated item through."""
    server.store("a")
    server.store("b")
    await hass.config_entries.async_setup(config_entry.entry_id)
    saving, release = threading.Event(), threading.Event()

    def save_on_release(url: str, data: str, headers: dict[str, str]) -> MagicMock:
        dav_client.put.side_effect = server.put
        saving.set()
        release.wait(5)
        return server.put(url, data, headers)

    dav_client.put.side_effect = save_on_release
    rename = hass.async_create_task(update_item(hass, "b", **{ATTR_RENAME: "renamed"}))
    await hass.async_add_executor_job(saving.wait, 5)
    waiting = hass.async_create_task(
        hass.services.async_call(
            TODO_DOMAIN,
            service,
            data,
            target={TargetKey.ENTITY_ID: TEST_ENTITY},
            blocking=True,
        )
    )
    await asyncio.sleep(0)
    server.store("a", "DESCRIPTION:Added elsewhere")
    await async_update_entity(hass, TEST_ENTITY)
    release.set()
    await rename

    with pytest.raises(HomeAssistantError) as err:
        await waiting
    assert err.value.translation_key == "item_changed"
    assert "DESCRIPTION:Added elsewhere" in server.todos["a"]
