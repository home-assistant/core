"""Unit tests for the Todoist calendar platform."""
from unittest.mock import AsyncMock, patch

import pytest
from todoist_api_python.models import Due, Label, Project, Task

from homeassistant import setup
from homeassistant.components.todoist.calendar import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
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
async def test_calendar_entity_unique_id(todoist_api, hass: HomeAssistant, api) -> None:
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
    assert entity.unique_id == "12345"


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_calendar_custom_project_unique_id(
    todoist_api, hass: HomeAssistant, api
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

    registry = entity_registry.async_get(hass)
    entity = registry.async_get("calendar.all_projects")
    assert entity is None

    state = hass.states.get("calendar.all_projects")
    assert state.state == "off"
