"""Common fixtures for the todoist tests."""

from collections.abc import AsyncGenerator, Callable, Generator
from http import HTTPStatus
from typing import TypeVar
from unittest.mock import AsyncMock, patch

import pytest
from requests.exceptions import HTTPError
from requests.models import Response
from todoist_api_python.models import Collaborator, Due, Label, Project, Section, Task

from homeassistant.components.todoist import DOMAIN
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

T = TypeVar("T")

PROJECT_ID = "project-id-1"
SECTION_ID = "section-id-1"
SUMMARY = "A task"
TOKEN = "some-token"


async def _async_generator(items: list[T]) -> AsyncGenerator[list[T]]:
    """Create an async generator that yields items as a single page."""
    yield items


def make_api_response(items: list[T]) -> Callable[[], AsyncGenerator[list[T]]]:
    """Create a callable that returns a fresh async generator each time.

    This is needed because async generators can only be iterated once,
    but mocks may be called multiple times.
    """

    async def _generator(*args, **kwargs) -> AsyncGenerator[list[T]]:
        async for page in _async_generator(items):
            yield page

    return _generator


def make_api_due(
    date: str,
    is_recurring: bool = False,
    string: str = "",
    timezone: str | None = None,
) -> Due:
    """Create a Due object using from_dict to match API deserialization behavior.

    This ensures the date field is properly converted to date/datetime objects
    just like the real API response deserialization does.
    """
    data: dict = {
        "date": date,
        "is_recurring": is_recurring,
        "string": string,
    }
    if timezone is not None:
        data["timezone"] = timezone
    return Due.from_dict(data)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.todoist.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="due")
def mock_due() -> Due:
    """Mock a todoist Task Due date/time.

    Uses a fixed date matching the frozen test time in test_calendar.py
    and test_todo.py (2024-05-24 12:00:00).
    """
    return make_api_due(date="2024-05-24", string="today")


def make_api_task(
    id: str | None = None,
    content: str | None = None,
    completed_at: str | None = None,
    due: Due | None = None,
    project_id: str | None = None,
    description: str | None = None,
    parent_id: str | None = None,
) -> Task:
    """Mock a todoist Task instance."""
    return Task(
        assignee_id="1",
        assigner_id="1",
        completed_at=completed_at,
        content=content or SUMMARY,
        created_at="2021-10-01T00:00:00",
        creator_id="1",
        description=description or "",
        due=due,
        id=id or "1",
        labels=["Label1"],
        order=1,
        parent_id=parent_id,
        priority=1,
        project_id=project_id or PROJECT_ID,
        section_id=None,
        duration=None,
        deadline=None,
        is_collapsed=False,
        updated_at="2021-10-01T00:00:00",
    )


@pytest.fixture(name="tasks")
def mock_tasks(due: Due) -> list[Task]:
    """Mock a todoist Task instance."""
    return [make_api_task(due=due)]


@pytest.fixture(name="api")
def mock_api(tasks: list[Task]) -> AsyncMock:
    """Mock the api state."""
    api = AsyncMock()
    api.get_projects.side_effect = make_api_response(
        [
            Project(
                id=PROJECT_ID,
                color="blue",
                is_favorite=False,
                name="Name",
                is_shared=False,
                is_archived=False,
                is_collapsed=False,
                is_inbox_project=False,
                can_assign_tasks=False,
                order=1,
                parent_id=None,
                view_style="list",
                description="",
                created_at="2021-01-01",
                updated_at="2021-01-01",
            )
        ]
    )
    api.get_sections.side_effect = make_api_response(
        [
            Section(
                id=SECTION_ID,
                project_id=PROJECT_ID,
                name="Section Name",
                order=1,
                is_collapsed=False,
            )
        ]
    )
    api.get_labels.side_effect = make_api_response(
        [Label(id="1", name="Label1", color="1", order=1, is_favorite=False)]
    )
    api.get_collaborators.side_effect = make_api_response(
        [Collaborator(email="user@gmail.com", id="1", name="user")]
    )
    api.get_tasks.side_effect = make_api_response(tasks)
    return api


@pytest.fixture(name="todoist_api_status")
def mock_api_status() -> HTTPStatus | None:
    """Fixture to inject an http status error."""
    return None


@pytest.fixture(autouse=True)
def mock_api_side_effect(
    api: AsyncMock, todoist_api_status: HTTPStatus | None
) -> MockConfigEntry:
    """Mock todoist configuration."""
    if todoist_api_status:
        response = Response()
        response.status_code = todoist_api_status
        api.get_tasks.side_effect = HTTPError(response=response)


@pytest.fixture(name="todoist_config_entry")
def mock_todoist_config_entry() -> MockConfigEntry:
    """Mock todoist configuration."""
    return MockConfigEntry(domain=DOMAIN, unique_id=TOKEN, data={CONF_TOKEN: TOKEN})


@pytest.fixture(name="todoist_domain")
def mock_todoist_domain() -> str:
    """Mock todoist configuration."""
    return DOMAIN


@pytest.fixture(autouse=True)
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    platforms: list[Platform],
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Mock setup of the todoist integration."""
    if todoist_config_entry is not None:
        todoist_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.todoist.TodoistAPIAsync", return_value=api),
        patch("homeassistant.components.todoist.PLATFORMS", platforms),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield
