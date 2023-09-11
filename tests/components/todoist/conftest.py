"""Common fixtures for the todoist tests."""
from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from requests.exceptions import HTTPError
from requests.models import Response
from todoist_api_python.models import Collaborator, Due, Label, Project, Task

from homeassistant.components.todoist import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

SUMMARY = "A task"
TOKEN = "some-token"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.todoist.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="due")
def mock_due() -> Due:
    """Mock a todoist Task Due date/time."""
    return Due(
        is_recurring=False, date=dt_util.now().strftime("%Y-%m-%d"), string="today"
    )


@pytest.fixture(name="task")
def mock_task(due: Due) -> Task:
    """Mock a todoist Task instance."""
    return Task(
        assignee_id="1",
        assigner_id="1",
        comment_count=0,
        is_completed=False,
        content=SUMMARY,
        created_at="2021-10-01T00:00:00",
        creator_id="1",
        description="A task",
        due=due,
        id="1",
        labels=["Label1"],
        order=1,
        parent_id=None,
        priority=1,
        project_id="12345",
        section_id=None,
        url="https://todoist.com",
        sync_id=None,
    )


@pytest.fixture(name="api")
def mock_api(task) -> AsyncMock:
    """Mock the api state."""
    api = AsyncMock()
    api.get_projects.return_value = [
        Project(
            id="12345",
            color="blue",
            comment_count=0,
            is_favorite=False,
            name="Name",
            is_shared=False,
            url="",
            is_inbox_project=False,
            is_team_inbox=False,
            order=1,
            parent_id=None,
            view_style="list",
        )
    ]
    api.get_labels.return_value = [
        Label(id="1", name="Label1", color="1", order=1, is_favorite=False)
    ]
    api.get_collaborators.return_value = [
        Collaborator(email="user@gmail.com", id="1", name="user")
    ]
    api.get_tasks.return_value = [task]
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


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Mock setup of the todoist integration."""
    if todoist_config_entry is not None:
        todoist_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.todoist.TodoistAPIAsync", return_value=api):
        assert await async_setup_component(hass, DOMAIN, {})
        yield
