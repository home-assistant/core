"""Common fixtures for the todoist tests (v3-compatible, object-style mocks)."""

from collections.abc import Generator
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from requests.exceptions import HTTPError
from requests.models import Response

from homeassistant.components.todoist import DOMAIN
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

PROJECT_ID = "project-id-1"
SECTION_ID = "section-id-1"
SUMMARY = "A task"
TOKEN = "some-token"
TODAY = dt_util.now().strftime("%Y-%m-%d")


def _make_due(date=None, datetime=None, string=None, is_recurring=False, lang="en"):
    """Return an object that mimics the Todoist Due model.

    Accepts old kwargs (datetime/timezone) but will store only fields we need.
    Tests may pass a real todoist_api_python.models.Due instance — we preserve it.
    """
    return SimpleNamespace(
        date=date,
        datetime=datetime,
        string=string,
        is_recurring=is_recurring,
        lang=lang,
    )


def _make_task(
    id="1",
    content=None,
    is_completed=False,
    due=None,
    project_id=PROJECT_ID,
    description=None,
    parent_id=None,
    priority=1,
):
    """Return an object that mimics a Todoist Task with attribute access."""
    return SimpleNamespace(
        id=id,
        content=content or SUMMARY,
        is_completed=is_completed,
        description=description,
        project_id=project_id,
        parent_id=parent_id,
        due=due,
        labels=["Label1"],
        created_at="2025-01-01T00:00:00Z",
        url="https://todoist.com",
        priority=priority,
    )


def _make_project(id=PROJECT_ID, name="Name", color="blue"):
    return SimpleNamespace(id=id, name=name, color=color)


def _make_section(id=SECTION_ID, project_id=PROJECT_ID, name="Section Name"):
    return SimpleNamespace(id=id, project_id=project_id, name=name)


def _make_label(id="1", name="Label1", color="1"):
    return SimpleNamespace(id=id, name=name, color=color)


def _make_collaborator(id="1", name="user", email="user@gmail.com"):
    return SimpleNamespace(id=id, name=name, email=email)


async def async_gen_single_page(page):
    """Yield a single page as an async generator.

    Used to mock paginated Todoist API responses that return only one page.
    """
    yield page


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.todoist.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="due")
def mock_due():
    """Mock a todoist Task Due-like object."""
    return _make_due(date=TODAY, string="today")


def make_api_task(
    id: str | None = None,
    content: str | None = None,
    is_completed: bool = False,
    due: object | None = None,
    project_id: str | None = None,
    description: str | None = None,
    parent_id: str | None = None,
    labels: list[str] | None = None,
    priority: int = 1,
):
    """Factory function used by tests that want Task-like objects."""
    description = description or ""
    task = _make_task(
        id=id or "1",
        content=content or SUMMARY,
        is_completed=is_completed,
        due=due,
        project_id=project_id or PROJECT_ID,
        description=description,
        parent_id=parent_id,
        priority=priority,
    )
    task.labels = labels if labels is not None else ["Label1"]
    return task


@pytest.fixture(name="tasks")
def mock_tasks(due) -> list:
    """Return a list of Task-like objects (single page)."""
    return [make_api_task(due=due)]


@pytest.fixture(name="api")
def mock_api(tasks: list):
    """Mock the Todoist v3 Async API returning object-like items and async generators."""
    api = AsyncMock()

    api.get_projects.return_value = async_gen_single_page([_make_project()])
    api.get_sections.return_value = async_gen_single_page([_make_section()])
    api.get_labels.return_value = async_gen_single_page([_make_label()])
    api.get_collaborators.return_value = async_gen_single_page([_make_collaborator()])

    api.get_tasks.return_value = async_gen_single_page(tasks)

    api.get_completed_tasks_by_due_date.return_value = async_gen_single_page([])

    api.add_task = AsyncMock()
    api.update_task = AsyncMock()
    api.complete_task = AsyncMock()
    api.uncomplete_task = AsyncMock()
    api.delete_task = AsyncMock()

    return api


@pytest.fixture(name="todoist_api_status")
def mock_api_status() -> HTTPStatus | None:
    """Fixture to inject an http status error."""
    return None


@pytest.fixture(autouse=True)
def mock_api_side_effect(api: AsyncMock, todoist_api_status: HTTPStatus | None):
    """Inject HTTPError on get_tasks if requested by a test fixture."""
    if todoist_api_status:
        response = Response()
        response.status_code = todoist_api_status
        api.get_tasks.side_effect = HTTPError(response=response)


@pytest.fixture(name="todoist_config_entry")
def mock_todoist_config_entry() -> MockConfigEntry:
    """Mock todoist configuration entry fixture."""
    return MockConfigEntry(domain=DOMAIN, unique_id=TOKEN, data={CONF_TOKEN: TOKEN})


@pytest.fixture(name="todoist_domain")
def mock_todoist_domain() -> str:
    """Fixture returning the Todoist domain."""
    return DOMAIN


@pytest.fixture(autouse=True)
def platforms() -> list[Platform]:
    """Override platforms default (tests set per-module)."""
    return []


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    platforms: list[Platform],
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Mock setup of the todoist integration (uses patched TodoistAPIAsync)."""
    if todoist_config_entry is not None:
        todoist_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.todoist.TodoistAPIAsync", return_value=api),
        patch("homeassistant.components.todoist.PLATFORMS", platforms),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield
