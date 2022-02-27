"""The tests for the google calendar platform."""

from __future__ import annotations

import copy
from http import HTTPStatus
from typing import Any
from unittest.mock import Mock, patch

import httplib2
import pytest

from homeassistant.components.google import (
    CONF_CAL_ID,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_ENTITIES,
    CONF_IGNORE_AVAILABILITY,
    CONF_NAME,
    CONF_TRACK,
    DEVICE_SCHEMA,
    SERVICE_SCAN_CALENDARS,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .conftest import TEST_CALENDAR

from tests.common import async_mock_service

GOOGLE_CONFIG = {CONF_CLIENT_ID: "client_id", CONF_CLIENT_SECRET: "client_secret"}
TEST_ENTITY = "calendar.we_are_we_are_a_test_calendar"
TEST_ENTITY_NAME = "We are, we are, a... Test Calendar"

TEST_EVENT = {
    "summary": "Test All Day Event",
    "start": {},
    "end": {},
    "location": "Test Cases",
    "description": "test event",
    "kind": "calendar#event",
    "created": "2016-06-23T16:37:57.000Z",
    "transparency": "transparent",
    "updated": "2016-06-24T01:57:21.045Z",
    "reminders": {"useDefault": True},
    "organizer": {
        "email": "uvrttabwegnui4gtia3vyqb@import.calendar.google.com",
        "displayName": "Organizer Name",
        "self": True,
    },
    "sequence": 0,
    "creator": {
        "email": "uvrttabwegnui4gtia3vyqb@import.calendar.google.com",
        "displayName": "Organizer Name",
        "self": True,
    },
    "id": "_c8rinwq863h45qnucyoi43ny8",
    "etag": '"2933466882090000"',
    "htmlLink": "https://www.google.com/calendar/event?eid=*******",
    "iCalUID": "cydrevtfuybguinhomj@google.com",
    "status": "confirmed",
}


def get_calendar_info(calendar):
    """Convert data from Google into DEVICE_SCHEMA."""
    calendar_info = DEVICE_SCHEMA(
        {
            CONF_CAL_ID: calendar["id"],
            CONF_ENTITIES: [
                {
                    CONF_TRACK: calendar["track"],
                    CONF_NAME: calendar["summary"],
                    CONF_DEVICE_ID: slugify(calendar["summary"]),
                    CONF_IGNORE_AVAILABILITY: calendar.get("ignore_availability", True),
                }
            ],
        }
    )
    return calendar_info


@pytest.fixture(autouse=True)
def mock_google_setup(hass, test_calendar, mock_token_read):
    """Mock the google set up functions."""
    hass.loop.run_until_complete(async_setup_component(hass, "group", {"group": {}}))
    calendar = get_calendar_info(test_calendar)
    calendars = {calendar[CONF_CAL_ID]: calendar}
    patch_google_load = patch(
        "homeassistant.components.google.load_config", return_value=calendars
    )
    patch_google_services = patch("homeassistant.components.google.setup_services")
    async_mock_service(hass, "google", SERVICE_SCAN_CALENDARS)

    with patch_google_load, patch_google_services:
        yield


@pytest.fixture(autouse=True)
def set_time_zone():
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    dt_util.set_default_time_zone(dt_util.get_time_zone("America/Regina"))
    yield
    dt_util.set_default_time_zone(dt_util.get_time_zone("UTC"))


def create_test_event(updates: dict[str, Any]) -> dict[str, Any]:
    """Create a test event with overrides from the default template."""
    event = copy.deepcopy(TEST_EVENT)
    event.update(updates)
    return event


def create_upcoming_event(updates: dict[str, Any]) -> dict[str, Any]:
    """Create a test event with an arbitrary start/end time."""
    now = dt_util.now()
    return create_test_event(
        {
            "start": {"dateTime": now.isoformat()},
            "end": {"dateTime": (now + dt_util.dt.timedelta(minutes=5)).isoformat()},
            **updates,
        }
    )


def get_event_api_url() -> str:
    """Return a calendar API to return active events."""
    now = dt_util.now()
    start = (now - dt_util.dt.timedelta(minutes=60)).isoformat()
    end = (now + dt_util.dt.timedelta(minutes=60)).isoformat()
    return f"/api/calendars/{TEST_ENTITY}?start={start}&end={end}"


async def test_all_day_event(hass, mock_events_list_items, mock_token_read):
    """Test that we can create an event trigger on device."""
    week_from_today = dt_util.dt.date.today() + dt_util.dt.timedelta(days=7)
    end_event = week_from_today + dt_util.dt.timedelta(days=1)
    event = create_test_event(
        {
            "start": {"date": week_from_today.isoformat()},
            "end": {"date": end_event.isoformat()},
        }
    )
    mock_events_list_items([event])

    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state.name == TEST_ENTITY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": TEST_ENTITY_NAME,
        "message": event["summary"],
        "all_day": True,
        "offset_reached": False,
        "start_time": week_from_today.strftime(DATE_STR_FORMAT),
        "end_time": end_event.strftime(DATE_STR_FORMAT),
        "location": event["location"],
        "description": event["description"],
    }


async def test_future_event(hass, mock_events_list_items):
    """Test that we can create an event trigger on device."""
    one_hour_from_now = dt_util.now() + dt_util.dt.timedelta(minutes=30)
    end_event = one_hour_from_now + dt_util.dt.timedelta(minutes=60)
    event = create_test_event(
        {
            "start": {"dateTime": one_hour_from_now.isoformat()},
            "end": {"dateTime": end_event.isoformat()},
        }
    )
    mock_events_list_items([event])

    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state.name == TEST_ENTITY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": TEST_ENTITY_NAME,
        "message": event["summary"],
        "all_day": False,
        "offset_reached": False,
        "start_time": one_hour_from_now.strftime(DATE_STR_FORMAT),
        "end_time": end_event.strftime(DATE_STR_FORMAT),
        "location": event["location"],
        "description": event["description"],
    }


async def test_in_progress_event(hass, mock_events_list_items):
    """Test that we can create an event trigger on device."""
    middle_of_event = dt_util.now() - dt_util.dt.timedelta(minutes=30)
    end_event = middle_of_event + dt_util.dt.timedelta(minutes=60)
    event = create_test_event(
        {
            "start": {"dateTime": middle_of_event.isoformat()},
            "end": {"dateTime": end_event.isoformat()},
        }
    )
    mock_events_list_items([event])

    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state.name == TEST_ENTITY_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": TEST_ENTITY_NAME,
        "message": event["summary"],
        "all_day": False,
        "offset_reached": False,
        "start_time": middle_of_event.strftime(DATE_STR_FORMAT),
        "end_time": end_event.strftime(DATE_STR_FORMAT),
        "location": event["location"],
        "description": event["description"],
    }


async def test_offset_in_progress_event(hass, mock_events_list_items):
    """Test that we can create an event trigger on device."""
    middle_of_event = dt_util.now() + dt_util.dt.timedelta(minutes=14)
    end_event = middle_of_event + dt_util.dt.timedelta(minutes=60)
    event_summary = "Test Event in Progress"
    event = create_test_event(
        {
            "start": {"dateTime": middle_of_event.isoformat()},
            "end": {"dateTime": end_event.isoformat()},
            "summary": f"{event_summary} !!-15",
        }
    )
    mock_events_list_items([event])

    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state.name == TEST_ENTITY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": TEST_ENTITY_NAME,
        "message": event_summary,
        "all_day": False,
        "offset_reached": True,
        "start_time": middle_of_event.strftime(DATE_STR_FORMAT),
        "end_time": end_event.strftime(DATE_STR_FORMAT),
        "location": event["location"],
        "description": event["description"],
    }


@pytest.mark.skip
async def test_all_day_offset_in_progress_event(hass, mock_events_list_items):
    """Test that we can create an event trigger on device."""
    tomorrow = dt_util.dt.date.today() + dt_util.dt.timedelta(days=1)
    end_event = tomorrow + dt_util.dt.timedelta(days=1)
    event_summary = "Test All Day Event Offset In Progress"
    event = create_test_event(
        {
            "start": {"date": tomorrow.isoformat()},
            "end": {"date": end_event.isoformat()},
            "summary": f"{event_summary} !!-25:0",
        }
    )
    mock_events_list_items([event])

    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state.name == TEST_ENTITY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": TEST_ENTITY_NAME,
        "message": event_summary,
        "all_day": True,
        "offset_reached": True,
        "start_time": tomorrow.strftime(DATE_STR_FORMAT),
        "end_time": end_event.strftime(DATE_STR_FORMAT),
        "location": event["location"],
        "description": event["description"],
    }


async def test_all_day_offset_event(hass, mock_events_list_items):
    """Test that we can create an event trigger on device."""
    tomorrow = dt_util.dt.date.today() + dt_util.dt.timedelta(days=2)
    end_event = tomorrow + dt_util.dt.timedelta(days=1)
    offset_hours = 1 + dt_util.now().hour
    event_summary = "Test All Day Event Offset"
    event = create_test_event(
        {
            "start": {"date": tomorrow.isoformat()},
            "end": {"date": end_event.isoformat()},
            "summary": f"{event_summary} !!-{offset_hours}:0",
        }
    )
    mock_events_list_items([event])

    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state.name == TEST_ENTITY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": TEST_ENTITY_NAME,
        "message": event_summary,
        "all_day": True,
        "offset_reached": False,
        "start_time": tomorrow.strftime(DATE_STR_FORMAT),
        "end_time": end_event.strftime(DATE_STR_FORMAT),
        "location": event["location"],
        "description": event["description"],
    }


async def test_update_error(hass, calendar_resource):
    """Test that the calendar handles a server error."""
    calendar_resource.return_value.get = Mock(
        side_effect=httplib2.ServerNotFoundError("unit test")
    )
    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state.name == TEST_ENTITY_NAME
    assert state.state == "off"


async def test_calendars_api(hass, hass_client):
    """Test the Rest API returns the calendar."""
    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get("/api/calendars")
    assert response.status == HTTPStatus.OK
    data = await response.json()
    assert data == [
        {
            "entity_id": TEST_ENTITY,
            "name": TEST_ENTITY_NAME,
        }
    ]


async def test_http_api_event(hass, hass_client, mock_events_list_items):
    """Test querying the API and fetching events from the server."""
    event = create_upcoming_event({"summary": "Event title"})
    mock_events_list_items([event])
    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(get_event_api_url())
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert len(events) == 1
    assert "summary" in events[0]
    assert events[0]["summary"] == "Event title"


async def test_http_event_api_failure(hass, hass_client, calendar_resource):
    """Test the Rest API response during a calendar failure."""
    calendar_resource.side_effect = httplib2.ServerNotFoundError("unit test")

    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(get_event_api_url())
    assert response.status == HTTPStatus.OK
    # A failure to talk to the server results in an empty list of events
    events = await response.json()
    assert events == []


def create_ignore_avail_calendar() -> dict[str, Any]:
    """Create a calendar with ignore_availability set."""
    calendar = TEST_CALENDAR.copy()
    calendar["ignore_availability"] = False
    return calendar


@pytest.mark.parametrize(
    "test_calendar,transparency,expect_visible_event",
    [
        (create_ignore_avail_calendar(), "opaque", True),
        (create_ignore_avail_calendar(), "transparent", False),
    ],
)
async def test_opaque_event(
    hass, hass_client, mock_events_list_items, transparency, expect_visible_event
):
    """Test querying the API and fetching events from the server."""
    event = create_upcoming_event({"transparency": transparency})
    mock_events_list_items([event])
    assert await async_setup_component(hass, "google", {"google": GOOGLE_CONFIG})
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(get_event_api_url())
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert (len(events) > 0) == expect_visible_event
