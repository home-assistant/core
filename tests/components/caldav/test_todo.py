"""The tests for the webdav todo component."""
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, Mock

from caldav.objects import Todo
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

CALENDAR_NAME = "My Tasks"
ENTITY_NAME = "My tasks"
TEST_ENTITY = "todo.my_tasks"

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


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set up config entry platforms."""
    return [Platform.TODO]


@pytest.fixture(name="todos")
def mock_todos() -> list[str]:
    """Fixture to return VTODO objects for the calendar."""
    return []


@pytest.fixture(name="supported_components")
def mock_supported_components() -> list[str]:
    """Fixture to set supported components of the calendar."""
    return ["VTODO"]


@pytest.fixture(name="calendars")
def mock_calendars(todos: list[str], supported_components: list[str]) -> list[Mock]:
    """Fixture to create calendars for the test."""
    calendar = Mock()
    items = [
        Todo(None, f"{idx}.ics", item, calendar, str(idx))
        for idx, item in enumerate(todos)
    ]
    calendar.search = MagicMock(return_value=items)
    calendar.name = CALENDAR_NAME
    calendar.get_supported_components = MagicMock(return_value=supported_components)
    return [calendar]


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
    setup_integration: Callable[[], Awaitable[bool]],
    expected_state: str,
) -> None:
    """Test a calendar entity from a config entry."""
    assert await setup_integration()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == ENTITY_NAME
    assert state.state == expected_state
    assert dict(state.attributes) == {
        "friendly_name": ENTITY_NAME,
    }


@pytest.mark.parametrize(
    ("supported_components", "has_entity"),
    [([], False), (["VTODO"], True), (["VEVENT"], False), (["VEVENT", "VTODO"], True)],
)
async def test_supported_components(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    has_entity: bool,
) -> None:
    """Test a calendar supported components matches VTODO."""
    assert await setup_integration()

    state = hass.states.get(TEST_ENTITY)
    assert (state is not None) == has_entity
