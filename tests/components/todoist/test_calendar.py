"""Unit tests for the Todoist calendar platform."""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from todoist_api_python.models import Due, Label, Project, Task

from homeassistant import setup
from homeassistant.components.todoist.calendar import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity


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
        due=Due(
            is_recurring=False, date=datetime.now().strftime("%Y-%m-%d"), string="today"
        ),
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
    api.get_collaborators.return_value = []
    api.get_tasks.return_value = [task]
    return api


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
async def test_update_entity_for_custom_project_with_labels_on(todoist_api, hass, api):
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
