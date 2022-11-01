"""Unit tests for the Todoist calendar platform."""
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant import setup
from homeassistant.components.todoist.calendar import DOMAIN, _parse_due_date
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import entity_registry
from homeassistant.util import dt


class MockDue:
    """Mock a Todoist due date."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize the mock."""
        self.date = data["date"]
        self.is_recurring = data["is_recurring"]
        self.datetime = data["datetime"]
        self.string = data["string"]
        self.timezone = data["timezone"]


def test_parse_due_date_invalid():
    """Test None is returned if the due date can't be parsed."""
    data = {
        "date": "invalid",
        "is_recurring": False,
        "datetime": "invalid",
        "string": "",
        "timezone": None,
    }
    due = MockDue(data)
    assert _parse_due_date(due) is None


def test_parse_due_date_without_timezone():
    """Test due date is parsed correctly when it has no timezone."""
    data = {
        "date": "2022-02-02",
        "is_recurring": False,
        "datetime": "2022-02-02T14:00:00Z",
        "string": "Feb 2 2:00 PM",
        "timezone": None,
    }
    due = MockDue(data)
    actual = _parse_due_date(due)
    assert datetime(2022, 2, 2, 14, 0, 0, tzinfo=dt.UTC) == actual


def test_parse_due_date_with_timezone():
    """Test due date is parsed correctly when it has a timezone."""
    data = {
        "date": "2022-02-02",
        "is_recurring": False,
        "datetime": "2022-02-02T14:00:00Z",
        "string": "Feb 2 2:00 PM",
        "timezone": "America/New_York",
    }
    due = MockDue(data)
    actual = _parse_due_date(due)
    # 2 p.m. in New York is 6:56 p.m. UTC
    assert datetime(2022, 2, 2, 18, 56, 0, tzinfo=dt.UTC) == actual


@pytest.fixture(name="state")
def mock_state() -> dict[str, Any]:
    """Mock the api state."""
    return {
        "collaborators": [],
        "labels": [{"name": "label1", "id": 1}],
        "projects": [{"id": 12345, "name": "Name"}],
    }


@patch("homeassistant.components.todoist.calendar.TodoistAPI")
async def test_calendar_entity_unique_id(todoist_api, hass, state):
    """Test unique id is set to project id."""
    api = Mock(state=state)
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
    assert 12345 == entity.unique_id


@patch("homeassistant.components.todoist.calendar.TodoistAPI")
async def test_calendar_custom_project_unique_id(todoist_api, hass, state):
    """Test unique id is None for any custom projects."""
    api = Mock(state=state)
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
