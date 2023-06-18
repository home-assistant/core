"""The tests for the calendar component."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.calendar import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util

from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_events_http_api(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    start = dt_util.now()
    end = start + timedelta(days=1)
    response = await client.get(
        f"/api/calendars/calendar.calendar_1?start={start.isoformat()}&end={end.isoformat()}"
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert events[0]["summary"] == "Future Event"


async def test_events_http_api_missing_fields(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    response = await client.get("/api/calendars/calendar.calendar_2")
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_events_http_api_error(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
            f"/api/calendars/calendar.calendar_1?start={start.isoformat()}&end={end.isoformat()}"
        )
        assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert await response.json() == {"message": "Error reading events: Failure"}


async def test_events_http_api_dates_wrong_order(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the calendar demo view."""
    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()
    client = await hass_client()
    start = dt_util.now()
    end = start + timedelta(days=-1)
    response = await client.get(
        f"/api/calendars/calendar.calendar_1?start={start.isoformat()}&end={end.isoformat()}"
    )
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_calendars_http_api(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
    ("payload", "code"),
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
async def test_unsupported_websocket(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, payload, code
) -> None:
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


async def test_unsupported_create_event_service(hass: HomeAssistant) -> None:
    """Test unsupported service call."""

    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="does not support this service"):
        await hass.services.async_call(
            DOMAIN,
            "create_event",
            {
                "start_date_time": "1997-07-14T17:00:00+00:00",
                "end_date_time": "1997-07-15T04:00:00+00:00",
                "summary": "Bastille Day Party",
            },
            target={"entity_id": "calendar.calendar_1"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("date_fields", "expected_error", "error_match"),
    [
        (
            {},
            vol.error.MultipleInvalid,
            "must contain at least one of start_date, start_date_time, in",
        ),
        (
            {
                "start_date": "2022-04-01",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "end_date": "2022-04-02",
            },
            vol.error.MultipleInvalid,
            "must contain at least one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date_time": "2022-04-01T06:00:00",
            },
            vol.error.MultipleInvalid,
            "Start and end datetimes must both be specified",
        ),
        (
            {
                "end_date_time": "2022-04-02T07:00:00",
            },
            vol.error.MultipleInvalid,
            "must contain at least one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date": "2022-04-01",
                "start_date_time": "2022-04-01T06:00:00",
                "end_date_time": "2022-04-02T07:00:00",
            },
            vol.error.MultipleInvalid,
            "must contain at most one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date_time": "2022-04-01T06:00:00",
                "end_date_time": "2022-04-01T07:00:00",
                "end_date": "2022-04-02",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "start_date": "2022-04-01",
                "end_date_time": "2022-04-02T07:00:00",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "start_date_time": "2022-04-01T07:00:00",
                "end_date": "2022-04-02",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "in": {
                    "days": 2,
                    "weeks": 2,
                }
            },
            vol.error.MultipleInvalid,
            "two or more values in the same group of exclusion 'event_types'",
        ),
        (
            {
                "start_date": "2022-04-01",
                "end_date": "2022-04-02",
                "in": {
                    "days": 2,
                },
            },
            vol.error.MultipleInvalid,
            "must contain at most one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date_time": "2022-04-01T07:00:00",
                "end_date_time": "2022-04-01T07:00:00",
                "in": {
                    "days": 2,
                },
            },
            vol.error.MultipleInvalid,
            "must contain at most one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date_time": "2022-04-01T06:00:00+00:00",
                "end_date_time": "2022-04-01T07:00:00+01:00",
            },
            vol.error.MultipleInvalid,
            "Expected all values to have the same timezone",
        ),
        (
            {
                "start_date_time": "2022-04-01T07:00:00",
                "end_date_time": "2022-04-01T06:00:00",
            },
            vol.error.MultipleInvalid,
            "Expected minimum event duration",
        ),
        (
            {
                "start_date": "2022-04-02",
                "end_date": "2022-04-01",
            },
            vol.error.MultipleInvalid,
            "Expected minimum event duration",
        ),
        (
            {
                "start_date": "2022-04-01",
                "end_date": "2022-04-01",
            },
            vol.error.MultipleInvalid,
            "Expected minimum event duration",
        ),
    ],
    ids=[
        "missing_all",
        "missing_end_date",
        "missing_start_date",
        "missing_end_datetime",
        "missing_start_datetime",
        "multiple_start",
        "multiple_end",
        "missing_end_date",
        "missing_end_date_time",
        "multiple_in",
        "unexpected_in_with_date",
        "unexpected_in_with_datetime",
        "inconsistent_timezone",
        "incorrect_date_order",
        "incorrect_datetime_order",
        "dates_not_exclusive",
    ],
)
async def test_create_event_service_invalid_params(
    hass: HomeAssistant,
    date_fields: dict[str, Any],
    expected_error: type[Exception],
    error_match: str | None,
):
    """Test creating an event using the create_event service."""

    await async_setup_component(hass, "calendar", {"calendar": {"platform": "demo"}})
    await hass.async_block_till_done()

    with pytest.raises(expected_error, match=error_match):
        await hass.services.async_call(
            "calendar",
            "create_event",
            {
                "summary": "Bastille Day Party",
                **date_fields,
            },
            target={"entity_id": "calendar.calendar_1"},
            blocking=True,
        )
