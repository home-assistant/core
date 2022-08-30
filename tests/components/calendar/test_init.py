"""The tests for the calendar component."""
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util


async def test_events_http_api(hass, hass_client):
    """Test the calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    start = dt_util.now()
    end = start + timedelta(days=1)
    response = await client.get(
        "/api/calendars/calendar.calendar_1?start={}&end={}".format(
            start.isoformat(), end.isoformat()
        )
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert events[0]["summary"] == "Future Event"


async def test_events_http_api_missing_fields(hass, hass_client):
    """Test the calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    response = await client.get("/api/calendars/calendar.calendar_2")
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_events_http_api_error(hass, hass_client):
    """Test the calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    start = dt_util.now()
    end = start + timedelta(days=1)

    with patch(
        "homeassistant.components.demo.calendar.DemoCalendar.async_get_events",
        side_effect=HomeAssistantError("Failure"),
    ):
        response = await client.get(
            "/api/calendars/calendar.calendar_1?start={}&end={}".format(
                start.isoformat(), end.isoformat()
            )
        )
        assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert await response.json() == {"message": "Error reading events: Failure"}


async def test_calendars_http_api(hass, hass_client):
    """Test the calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    response = await client.get("/api/calendars")
    assert response.status == HTTPStatus.OK
    data = await response.json()
    assert data == [
        {"entity_id": "calendar.calendar_1", "name": "Calendar 1"},
        {"entity_id": "calendar.calendar_2", "name": "Calendar 2"},
        {"entity_id": "calendar.calendar_3", "name": "Calendar 3"},
    ]


async def test_events_http_api_shim(hass, hass_client):
    """Test the legacy shim calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    response = await client.get("/api/calendars/calendar.calendar_3")
    assert response.status == HTTPStatus.BAD_REQUEST
    start = dt_util.now()
    end = start + timedelta(days=1)
    response = await client.get(
        "/api/calendars/calendar.calendar_1?start={}&end={}".format(
            start.isoformat(), end.isoformat()
        )
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert events[0]["summary"] == "Future Event"
    assert events[0]["description"] == "Future Description"
    assert events[0]["location"] == "Future Location"
