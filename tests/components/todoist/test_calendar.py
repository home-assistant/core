"""Unit tests for the Todoist calendar platform."""
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
import urllib

import pytest
from todoist_api_python.models import Collaborator, Due, Label, Project, Task

from homeassistant import setup
from homeassistant.components.todoist.const import (
    ASSIGNEE,
    CONTENT,
    DOMAIN,
    LABELS,
    PROJECT_NAME,
    SERVICE_NEW_TASK,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt

from tests.typing import ClientSessionGenerator


@pytest.fixture(name="task")
def mock_task() -> Task:
    """Mock a todoist Task instance."""
    return Task(
        assignee_id="1",
        assigner_id="1",
        comment_count=0,
        is_completed=False,
        content="A task",
        created_at="2021-10-01T00:00:00",
        creator_id="1",
        description="A task",
        due=Due(is_recurring=False, date=dt.now().strftime("%Y-%m-%d"), string="today"),
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


def get_events_url(entity: str, start: str, end: str) -> str:
    """Create a url to get events during the specified time range."""
    return f"/api/calendars/{entity}?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}"


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_calendar_entity_unique_id(
    todoist_api, hass: HomeAssistant, api, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id is set to project id."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
            }
        },
    )
    await hass.async_block_till_done()

    entity = entity_registry.async_get("calendar.name")
    assert entity.unique_id == "12345"


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_update_entity_for_custom_project_with_labels_on(
    todoist_api, hass: HomeAssistant, api
) -> None:
    """Test that the calendar's state is on for a custom project using labels."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
                "custom_projects": [{"name": "All projects", "labels": ["Label1"]}],
            }
        },
    )
    await hass.async_block_till_done()

    await async_update_entity(hass, "calendar.all_projects")
    state = hass.states.get("calendar.all_projects")
    assert state.attributes["labels"] == ["Label1"]
    assert state.state == "on"


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_failed_coordinator_update(todoist_api, hass: HomeAssistant, api) -> None:
    """Test a failed data coordinator update is handled correctly."""
    api.get_tasks.side_effect = Exception("API error")
    todoist_api.return_value = api

    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
                "custom_projects": [{"name": "All projects", "labels": ["Label1"]}],
            }
        },
    )
    await hass.async_block_till_done()

    await async_update_entity(hass, "calendar.all_projects")
    state = hass.states.get("calendar.all_projects")
    assert state is None


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_calendar_custom_project_unique_id(
    todoist_api, hass: HomeAssistant, api, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id is None for any custom projects."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
                "custom_projects": [{"name": "All projects"}],
            }
        },
    )
    await hass.async_block_till_done()

    entity = entity_registry.async_get("calendar.all_projects")
    assert entity is None

    state = hass.states.get("calendar.all_projects")
    assert state.state == "off"


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_all_day_event(
    todoist_api, hass: HomeAssistant, hass_client: ClientSessionGenerator, api
) -> None:
    """Test for an all day calendar event."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
                "custom_projects": [{"name": "All projects", "labels": ["Label1"]}],
            }
        },
    )
    await hass.async_block_till_done()

    await async_update_entity(hass, "calendar.all_projects")
    client = await hass_client()
    start = dt.now() - timedelta(days=1)
    end = dt.now() + timedelta(days=1)
    response = await client.get(
        get_events_url("calendar.all_projects", start.isoformat(), end.isoformat())
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()

    expected = [
        {
            "start": {"date": dt.now().strftime("%Y-%m-%d")},
            "end": {"date": (dt.now() + timedelta(days=1)).strftime("%Y-%m-%d")},
            "summary": "A task",
            "description": None,
            "location": None,
            "uid": None,
            "recurrence_id": None,
            "rrule": None,
        }
    ]
    assert events == expected


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_create_task_service_call(todoist_api, hass: HomeAssistant, api) -> None:
    """Test api is called correctly after a new task service call."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NEW_TASK,
        {ASSIGNEE: "user", CONTENT: "task", LABELS: ["Label1"], PROJECT_NAME: "Name"},
    )
    await hass.async_block_till_done()

    api.add_task.assert_called_with(
        "task", project_id="12345", labels=["Label1"], assignee_id="1"
    )
