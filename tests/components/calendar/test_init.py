"""The tests for the calendar component."""
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest

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
    ]


@pytest.mark.parametrize(
    "payload,code",
    [
        (
            {
                "type": "calendar/event/create",
                "entity_id": "calendar.calendar_1",
                "event": {
                    "summary": "Bastille Day Party",
                    "dtstart": "1997-07-14T17:00:00+00:00",
                    "dtend": "1997-07-15T04:00:00+00:00",
                },
            },
            "not_supported",
        ),
        (
            {
                "type": "calendar/event/create",
                "entity_id": "calendar.calendar_99",
                "event": {
                    "summary": "Bastille Day Party",
                    "dtstart": "1997-07-14T17:00:00+00:00",
                    "dtend": "1997-07-15T04:00:00+00:00",
                },
            },
            "not_found",
        ),
        (
            {
                "type": "calendar/event/delete",
                "entity_id": "calendar.calendar_1",
                "uid": "some-uid",
            },
            "not_supported",
        ),
        (
            {
                "type": "calendar/event/delete",
                "entity_id": "calendar.calendar_99",
                "uid": "some-uid",
            },
            "not_found",
        ),
        (
            {
                "type": "calendar/event/update",
                "entity_id": "calendar.calendar_1",
                "uid": "some-uid",
                "event": {
                    "summary": "Bastille Day Party",
                    "dtstart": "1997-07-14T17:00:00+00:00",
                    "dtend": "1997-07-15T04:00:00+00:00",
                },
            },
            "not_supported",
        ),
        (
            {
                "type": "calendar/event/update",
                "entity_id": "calendar.calendar_99",
                "uid": "some-uid",
                "event": {
                    "summary": "Bastille Day Party",
                    "dtstart": "1997-07-14T17:00:00+00:00",
                    "dtend": "1997-07-15T04:00:00+00:00",
                },
            },
            "not_found",
        ),
    ],
)
async def test_unsupported_websocket(hass, hass_ws_client, payload, code):
    """Test unsupported websocket command."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            **payload,
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("error")
    assert resp["error"].get("code") == code
