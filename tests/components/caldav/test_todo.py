"""The tests for the webdav todo component."""

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock, Mock

from caldav.lib.error import DAVError, NotFoundError
from caldav.objects import Todo
import pytest

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

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
def set_tz(hass: HomeAssistant) -> None:
    """Fixture to set timezone with fixed offset year round."""
    hass.config.set_time_zone("America/Regina")


@pytest.fixture(name="todos")
def mock_todos() -> list[str]:
    """Fixture to return VTODO objects for the calendar."""
    return []


@pytest.fixture(name="supported_components")
def mock_supported_components() -> list[str]:
    """Fixture to set supported components of the calendar."""
    return ["VTODO"]


@pytest.fixture(name="calendar")
def mock_calendar(supported_components: list[str]) -> Mock:
    """Fixture to create the primary calendar for the test."""
    calendar = Mock()
    calendar.search = MagicMock(return_value=[])
    calendar.name = CALENDAR_NAME
    calendar.get_supported_components = MagicMock(return_value=supported_components)
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
            {"due_date": "2023-11-18"},
            {"status": "NEEDS-ACTION", "summary": "Cheese", "due": date(2023, 11, 18)},
            {**RESULT_ITEM, "due": "2023-11-18"},
        ),
        (
            {"due_datetime": "2023-11-18T08:30:00-06:00"},
            {
                "status": "NEEDS-ACTION",
                "summary": "Cheese",
                "due": datetime(2023, 11, 18, 14, 30, 00, tzinfo=UTC),
            },
            {**RESULT_ITEM, "due": "2023-11-18T08:30:00-06:00"},
        ),
        (
            {"description": "Make sure to get Swiss"},
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
        "add_item",
        {"item": "Cheese", **item_data},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    assert calendar.save_todo.call_args
    assert calendar.save_todo.call_args.kwargs == expcted_save_args

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

    calendar.save_todo.side_effect = DAVError()

    with pytest.raises(HomeAssistantError, match="CalDAV save error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "add_item",
            {"item": "Cheese"},
            target={"entity_id": TEST_ENTITY},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("update_data", "expected_ics", "expected_state", "expected_item"),
    [
        (
            {"rename": "Swiss Cheese"},
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
            {"status": "needs_action"},
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
            {"status": "completed"},
            [
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
            },
        ),
        (
            {"rename": "Swiss Cheese", "status": "needs_action"},
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
            {"due_date": "2023-11-18"},
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
            {"due_datetime": "2023-11-18T08:30:00-06:00"},
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
            {"due_datetime": None},
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
            {"description": "Make sure to get Swiss"},
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
            {"description": None},
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

    calendar.todo_by_uid = MagicMock(return_value=item)

    dav_client.put.return_value.status = 204

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {
            "item": "Cheese",
            **update_data,
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )

    assert dav_client.put.call_args
    ics = dav_client.put.call_args.args[1]
    assert compact_ics(ics) == expected_ics

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == expected_state

    result = await hass.services.async_call(
        TODO_DOMAIN,
        "get_items",
        {},
        target={"entity_id": TEST_ENTITY},
        blocking=True,
        return_response=True,
    )
    assert result == {TEST_ENTITY: {"items": [expected_item]}}


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

    calendar.todo_by_uid = MagicMock(return_value=item)
    dav_client.put.side_effect = DAVError()

    with pytest.raises(HomeAssistantError, match="CalDAV save error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "update_item",
            {
                "item": "Cheese",
                "status": "completed",
            },
            target={"entity_id": TEST_ENTITY},
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

    calendar.todo_by_uid.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            TODO_DOMAIN,
            "update_item",
            {
                "item": "Cheese",
                "status": "completed",
            },
            target={"entity_id": TEST_ENTITY},
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

    calendar.todo_by_uid = Mock(side_effect=lookup)
    item1.delete = Mock()
    item2.delete = Mock()

    await hass.services.async_call(
        TODO_DOMAIN,
        "remove_item",
        {"item": uids_to_delete},
        target={"entity_id": TEST_ENTITY},
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

    calendar.todo_by_uid.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            TODO_DOMAIN,
            "remove_item",
            {"item": "Cheese"},
            target={"entity_id": TEST_ENTITY},
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

    calendar.todo_by_uid = Mock(side_effect=lookup)
    dav_client.delete.return_value.status = 500

    with pytest.raises(HomeAssistantError, match="CalDAV delete error"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "remove_item",
            {"item": "Cheese"},
            target={"entity_id": TEST_ENTITY},
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

    calendar.todo_by_uid.side_effect = NotFoundError()

    with pytest.raises(HomeAssistantError, match="Could not find"):
        await hass.services.async_call(
            TODO_DOMAIN,
            "remove_item",
            {"item": "Cheese"},
            target={"entity_id": TEST_ENTITY},
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

    calendar.todo_by_uid = MagicMock(return_value=item)
    dav_client.put.return_value.status = 204
    # Reflect update for state refresh after update
    calendar.search.return_value = [
        Todo(
            dav_client, None, TODO_NEEDS_ACTION.replace("Cheese", "Milk"), calendar, "2"
        )
    ]
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {
            "item": "Cheese",
            "rename": "Milk",
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
    assert items[0]["summary"] == "Milk"
    assert items[0]["status"] == "needs_action"
    assert items[0]["uid"]
