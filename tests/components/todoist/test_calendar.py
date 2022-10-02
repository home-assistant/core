"""Unit tests for the Todoist calendar platform."""
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest
from todoist_api_python.models import Due

from homeassistant import setup
from homeassistant.components.todoist.calendar import (
    DOMAIN,
    _parse_due_date,
    get_system_utc_offset_hours,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import entity_registry
from homeassistant.util import dt


@pytest.fixture(name="state")
def mock_state() -> dict[str, Any]:
    """Mock the api state."""
    return {
        "collaborators": [],
        "labels": [{"name": "label1", "id": 1}],
        "projects": [{"id": "12345", "name": "Name"}],
    }


def test_parse_due_date_invalid():
    """Test None is returned if the due date can't be parsed."""
    data = Due(date="invalid", recurring=False, string="")
    assert _parse_due_date(data, timezone_offset=-8) is None


def test_parse_due_date_with_no_time_data():
    """Test due date is parsed correctly when it has no time data."""
    data = Due(date="2022-02-02", recurring=False, string="Feb 2 2:00 PM")
    actual = _parse_due_date(data, timezone_offset=-8)
    assert datetime(2022, 2, 2, 8, 0, 0, tzinfo=dt.UTC) == actual


def test_parse_due_date_without_timezone_uses_offset():
    """Test due date uses user local timezone offset when it has no timezone."""
    data = Due(date="2022-02-02T14:00:00", recurring=False, string="Feb 2 2:00 PM")
    actual = _parse_due_date(data, timezone_offset=-8)
    assert datetime(2022, 2, 2, 22, 0, 0, tzinfo=dt.UTC) == actual


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
    assert "12345" == entity.unique_id


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


def test_get_system_utc_offset_hours_none():
    """Test 0 is returned if time_zone param is None."""
    assert get_system_utc_offset_hours(None) == 0


def test_get_system_utc_offset_hours_timezone_invalid():
    """Test 0 is returned if time_zone param is not a valid value."""
    assert get_system_utc_offset_hours("invalid") == 0


def test_get_system_utc_offset_hours_valid_timezone():
    """Test 0 is returned if time_zone param is not a valid value."""
    assert get_system_utc_offset_hours("America/Los_Angeles") == -7
