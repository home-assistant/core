"""Unit tests for the Todoist calendar platform."""
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch
import urllib
import zoneinfo

import pytest
from todoist_api_python.models import Due

from homeassistant import setup
from homeassistant.components.todoist.const import (
    ASSIGNEE,
    CONTENT,
    DOMAIN,
    LABELS,
    PROJECT_NAME,
    SERVICE_NEW_TASK,
)
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt as dt_util

from .conftest import PROJECT_ID, SUMMARY

from tests.typing import ClientSessionGenerator

# Set our timezone to CST/Regina so we can check calculations
# This keeps UTC-6 all year round
TZ_NAME = "America/Regina"
TIMEZONE = zoneinfo.ZoneInfo(TZ_NAME)


@pytest.fixture(autouse=True)
def platforms() -> list[Platform]:
    """Override platforms."""
    return [Platform.CALENDAR]


@pytest.fixture(autouse=True)
def set_time_zone(hass: HomeAssistant):
    """Set the time zone for the tests."""
    hass.config.set_time_zone(TZ_NAME)


def get_events_url(entity: str, start: str, end: str) -> str:
    """Create a url to get events during the specified time range."""
    return f"/api/calendars/{entity}?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}"


def get_events_response(start: dict[str, str], end: dict[str, str]) -> dict[str, Any]:
    """Return an event response with a single task."""
    return {
        "start": start,
        "end": end,
        "summary": SUMMARY,
        "description": None,
        "location": None,
        "uid": None,
        "recurrence_id": None,
        "rrule": None,
    }


@pytest.fixture(name="todoist_config")
def mock_todoist_config() -> dict[str, Any]:
    """Mock todoist configuration."""
    return {}


@pytest.fixture(name="setup_platform", autouse=True)
async def mock_setup_platform(
    hass: HomeAssistant,
    api: AsyncMock,
    todoist_config: dict[str, Any],
) -> None:
    """Mock setup of the todoist integration."""
    with patch(
        "homeassistant.components.todoist.calendar.TodoistAPIAsync"
    ) as todoist_api:
        todoist_api.return_value = api
        assert await setup.async_setup_component(
            hass,
            "calendar",
            {
                "calendar": {
                    "platform": DOMAIN,
                    CONF_TOKEN: "token",
                    **todoist_config,
                }
            },
        )
        await hass.async_block_till_done()
        await async_update_entity(hass, "calendar.name")
        yield


async def test_calendar_entity_unique_id(
    hass: HomeAssistant, api: AsyncMock, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id is set to project id."""
    entity = entity_registry.async_get("calendar.name")
    assert entity.unique_id == PROJECT_ID


@pytest.mark.parametrize(
    "todoist_config",
    [{"custom_projects": [{"name": "All projects", "labels": ["Label1"]}]}],
)
async def test_update_entity_for_custom_project_with_labels_on(
    hass: HomeAssistant,
    api: AsyncMock,
) -> None:
    """Test that the calendar's state is on for a custom project using labels."""
    await async_update_entity(hass, "calendar.all_projects")
    state = hass.states.get("calendar.all_projects")
    assert state.attributes["labels"] == ["Label1"]
    assert state.state == "on"


@pytest.mark.parametrize("due", [None])
async def test_update_entity_for_custom_project_no_due_date_on(
    hass: HomeAssistant,
    api: AsyncMock,
) -> None:
    """Test that a task without an explicit due date is considered to be in an on state."""
    await async_update_entity(hass, "calendar.name")
    state = hass.states.get("calendar.name")
    assert state.state == "on"


@pytest.mark.parametrize(
    "due",
    [
        Due(
            # Note: This runs before the test fixture that sets the timezone
            date=(dt_util.now(TIMEZONE) + timedelta(days=3)).strftime("%Y-%m-%d"),
            is_recurring=False,
            string="3 days from today",
        )
    ],
)
async def test_update_entity_for_calendar_with_due_date_in_the_future(
    hass: HomeAssistant,
    api: AsyncMock,
) -> None:
    """Test that a task with a due date in the future has on state and correct end_time."""
    await async_update_entity(hass, "calendar.name")
    state = hass.states.get("calendar.name")
    assert state.state == "on"

    # The end time should be in the user's timezone
    expected_end_time = (dt_util.now() + timedelta(days=3)).strftime(
        "%Y-%m-%d 00:00:00"
    )
    assert state.attributes["end_time"] == expected_end_time


@pytest.mark.parametrize("setup_platform", [None])
async def test_failed_coordinator_update(hass: HomeAssistant, api: AsyncMock) -> None:
    """Test a failed data coordinator update is handled correctly."""
    api.get_tasks.side_effect = Exception("API error")

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


@pytest.mark.parametrize(
    "todoist_config",
    [{"custom_projects": [{"name": "All projects"}]}],
)
async def test_calendar_custom_project_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id is None for any custom projects."""
    entity = entity_registry.async_get("calendar.all_projects")
    assert entity is None


@pytest.mark.parametrize(
    ("due", "start", "end", "expected_response"),
    [
        (
            Due(date="2023-03-30", is_recurring=False, string="Mar 30"),
            "2023-03-28T00:00:00.000Z",
            "2023-04-01T00:00:00.000Z",
            [get_events_response({"date": "2023-03-30"}, {"date": "2023-03-31"})],
        ),
        (
            Due(date="2023-03-30", is_recurring=False, string="Mar 30"),
            "2023-03-30T06:00:00.000Z",
            "2023-03-31T06:00:00.000Z",
            [get_events_response({"date": "2023-03-30"}, {"date": "2023-03-31"})],
        ),
        (
            Due(date="2023-03-30", is_recurring=False, string="Mar 30"),
            "2023-03-29T08:00:00.000Z",
            "2023-03-30T08:00:00.000Z",
            [get_events_response({"date": "2023-03-30"}, {"date": "2023-03-31"})],
        ),
        (
            Due(date="2023-03-30", is_recurring=False, string="Mar 30"),
            "2023-03-30T08:00:00.000Z",
            "2023-03-31T08:00:00.000Z",
            [get_events_response({"date": "2023-03-30"}, {"date": "2023-03-31"})],
        ),
        (
            Due(date="2023-03-30", is_recurring=False, string="Mar 30"),
            "2023-03-31T08:00:00.000Z",
            "2023-04-01T08:00:00.000Z",
            [],
        ),
        (
            Due(date="2023-03-30", is_recurring=False, string="Mar 30"),
            "2023-03-29T06:00:00.000Z",
            "2023-03-30T06:00:00.000Z",
            [],
        ),
    ],
    ids=("included", "exact", "overlap_start", "overlap_end", "after", "before"),
)
async def test_all_day_event(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    start: str,
    end: str,
    expected_response: dict[str, Any],
) -> None:
    """Test for an all day calendar event."""
    client = await hass_client()
    response = await client.get(
        get_events_url("calendar.name", start, end),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == expected_response


async def test_create_task_service_call(hass: HomeAssistant, api: AsyncMock) -> None:
    """Test api is called correctly after a new task service call."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NEW_TASK,
        {ASSIGNEE: "user", CONTENT: "task", LABELS: ["Label1"], PROJECT_NAME: "Name"},
    )
    await hass.async_block_till_done()

    api.add_task.assert_called_with(
        "task", project_id=PROJECT_ID, labels=["Label1"], assignee_id="1"
    )


@pytest.mark.parametrize(
    ("due"),
    [
        # These are all equivalent due dates for the same time in different
        # timezone formats.
        Due(
            date="2023-03-30",
            is_recurring=False,
            string="Mar 30 6:00 PM",
            datetime="2023-03-31T00:00:00Z",
            timezone="America/Regina",
        ),
        Due(
            date="2023-03-30",
            is_recurring=False,
            string="Mar 30 7:00 PM",
            datetime="2023-03-31T00:00:00Z",
            timezone="America/Los_Angeles",
        ),
        Due(
            date="2023-03-30",
            is_recurring=False,
            string="Mar 30 6:00 PM",
            datetime="2023-03-30T18:00:00",
        ),
    ],
    ids=("in_local_timezone", "in_other_timezone", "floating"),
)
async def test_task_due_datetime(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test for task due at a specific time, using different time formats."""
    client = await hass_client()

    has_task_response = [
        get_events_response(
            {"dateTime": "2023-03-30T18:00:00-06:00"},
            {"dateTime": "2023-03-31T18:00:00-06:00"},
        )
    ]

    # Completely includes the start/end of the task
    response = await client.get(
        get_events_url(
            "calendar.name", "2023-03-30T08:00:00.000Z", "2023-03-31T08:00:00.000Z"
        ),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == has_task_response

    # Overlap with the start of the event
    response = await client.get(
        get_events_url(
            "calendar.name", "2023-03-29T20:00:00.000Z", "2023-03-31T02:00:00.000Z"
        ),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == has_task_response

    # Overlap with the end of the event
    response = await client.get(
        get_events_url(
            "calendar.name", "2023-03-31T20:00:00.000Z", "2023-04-01T02:00:00.000Z"
        ),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == has_task_response

    # Task is active, but range does not include start/end
    response = await client.get(
        get_events_url(
            "calendar.name", "2023-03-31T10:00:00.000Z", "2023-03-31T11:00:00.000Z"
        ),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == has_task_response

    # Query is before the task starts (no results)
    response = await client.get(
        get_events_url(
            "calendar.name", "2023-03-28T00:00:00.000Z", "2023-03-29T00:00:00.000Z"
        ),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == []

    # Query is after the task ends (no results)
    response = await client.get(
        get_events_url(
            "calendar.name", "2023-04-01T07:00:00.000Z", "2023-04-02T07:00:00.000Z"
        ),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == []


@pytest.mark.parametrize(
    ("due", "setup_platform"),
    [
        (
            Due(
                date="2023-03-30",
                is_recurring=False,
                string="Mar 30 6:00 PM",
                datetime="2023-03-31T00:00:00Z",
                timezone="America/Regina",
            ),
            None,
        )
    ],
)
async def test_config_entry(
    hass: HomeAssistant,
    setup_integration: None,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test for a calendar created with a config entry."""

    await async_update_entity(hass, "calendar.name")
    state = hass.states.get("calendar.name")
    assert state

    client = await hass_client()
    response = await client.get(
        get_events_url(
            "calendar.name", "2023-03-30T08:00:00.000Z", "2023-03-31T08:00:00.000Z"
        ),
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == [
        get_events_response(
            {"dateTime": "2023-03-30T18:00:00-06:00"},
            {"dateTime": "2023-03-31T18:00:00-06:00"},
        )
    ]
