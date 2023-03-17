"""Test fixtures for the Todoist integration."""
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from todoist_api_python.models import Due, Label, Project, Task


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
