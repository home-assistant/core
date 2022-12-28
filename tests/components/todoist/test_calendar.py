"""Unit tests for the Todoist calendar platform."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from todoist_api_python.models import Due, Label, Project, Task

from homeassistant import setup
from homeassistant.components.calendar import CalendarEvent
from homeassistant.components.todoist.calendar import DOMAIN, TodoistProjectData
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import entity_registry


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
        due=Due(is_recurring=False, date="2022-01-01", string="today"),
        id="1",
        labels=[],
        order=1,
        parent_id=None,
        priority=1,
        project_id="12345",
        section_id=None,
        url="https://todoist.com",
        sync_id=None,
    )


@pytest.fixture(name="api")
def mock_api() -> AsyncMock:
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
        Label(id="1", name="label1", color="1", order=1, is_favorite=False)
    ]
    api.get_collaborators.return_value = []
    return api


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_calendar_entity_unique_id(todoist_api, hass, api):
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

    registry = entity_registry.async_get(hass)
    entity = registry.async_get("calendar.name")
    assert "12345" == entity.unique_id


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_calendar_custom_project_unique_id(todoist_api, hass, api):
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

    registry = entity_registry.async_get(hass)
    entity = registry.async_get("calendar.all_projects")
    assert entity is None

    state = hass.states.get("calendar.all_projects")
    assert state.state == "off"


async def test_async_get_events_no_due_date(api, task):
    """Test an event without a due date is ignored."""
    task.due = None
    api.get_tasks.return_value = [task]
    project_data = {"name": "test", "id": "12345"}
    todoist_project_data = TodoistProjectData(project_data, labels=[], api=api)

    start_date = datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    events = await todoist_project_data.async_get_events(start_date, end_date)

    assert [] == events


async def test_async_get_events_no_time_data(api, task):
    """Test an event with a due date between start/end without time data is returned."""
    task.due = Due(date="2022-01-01", is_recurring=False, string="")
    api.get_tasks.return_value = [task]
    project_data = {"name": "test", "id": "12345"}
    todoist_project_data = TodoistProjectData(
        project_data,
        labels=[],
        api=api,
    )

    start_date = datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    events = await todoist_project_data.async_get_events(start_date, end_date)

    expected = [
        CalendarEvent(
            summary=task.content, start=start_date.date(), end=start_date.date()
        )
    ]
    assert expected == events


async def test_async_get_events_with_time_data(api, task):
    """Test an event with a due date between start/end with time data is returned."""
    task.due = Due(
        date="2022-01-01", datetime="2022-01-01T16:00:00", is_recurring=False, string=""
    )
    api.get_tasks.return_value = [task]
    project_data = {"name": "test", "id": "12345"}
    todoist_project_data = TodoistProjectData(project_data, labels=[], api=api)

    start_date = datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    events = await todoist_project_data.async_get_events(start_date, end_date)

    expected_due_date = datetime(2022, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
    expected = [
        CalendarEvent(
            summary=task.content,
            start=expected_due_date,
            end=expected_due_date,
        )
    ]
    assert expected == events
