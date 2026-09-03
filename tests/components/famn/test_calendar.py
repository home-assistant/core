"""Tests for the Famn calendar platform."""

from datetime import datetime
from unittest.mock import AsyncMock

from famn_sdk import ApiError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import CALENDAR_ID

from tests.common import MockConfigEntry

ENTITY_ID = "calendar.home_assistant_familie"

pytestmark = [pytest.mark.usefixtures("mock_famn")]


async def test_calendar_entity_and_next_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the calendar entity exposes the next upcoming event."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Fotballtrening"
    assert state.attributes["location"] == "Idrettsparken"
    assert state.attributes["all_day"] is False


async def test_calendar_on_during_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the calendar state is on while an event is running."""
    freezer.move_to("2026-08-12T16:30:00Z")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_get_events_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_calendar_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fetching a range of events maps Famn occurrences correctly."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            EVENT_START_DATETIME: "2026-08-12T00:00:00Z",
            EVENT_END_DATETIME: "2026-08-17T00:00:00Z",
        },
        blocking=True,
        return_response=True,
    )

    events = result[ENTITY_ID]["events"]
    assert len(events) == 2

    timed = events[0]
    assert timed["summary"] == "Fotballtrening"
    assert timed["description"] == "Ta med leggskinn"
    assert timed["start"] == "2026-08-12T16:00:00+00:00"
    assert timed["end"] == "2026-08-12T17:30:00+00:00"

    # The all-day event covers two days: date-typed start, exclusive end.
    all_day = events[1]
    assert all_day["summary"] == "Hyttetur"
    assert all_day["start"] == "2026-08-14"
    assert all_day["end"] == "2026-08-16"

    # The range was passed through to Famn with server-side expansion.
    call = mock_calendar_api.get_calendar_events_endpoint.call_args
    assert call.args[0] == CALENDAR_ID
    assert call.kwargs["expand"] is True
    # Home Assistant hands the range over in local time, so compare the
    # instants rather than how they are spelled.
    assert dt_util.parse_datetime(call.kwargs["from_"]) == datetime(
        2026, 8, 12, tzinfo=dt_util.UTC
    )
    assert dt_util.parse_datetime(call.kwargs["to"]) == datetime(
        2026, 8, 17, tzinfo=dt_util.UTC
    )


async def test_get_events_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_calendar_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a Famn error surfaces as a Home Assistant error."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    mock_calendar_api.get_calendar_events_endpoint.side_effect = ApiError(500, "boom")

    with pytest.raises(HomeAssistantError, match="calendar events"):
        await hass.services.async_call(
            CALENDAR_DOMAIN,
            SERVICE_GET_EVENTS,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                EVENT_START_DATETIME: "2026-08-12T00:00:00Z",
                EVENT_END_DATETIME: "2026-08-17T00:00:00Z",
            },
            blocking=True,
            return_response=True,
        )


async def test_calendar_pagination(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_calendar_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that all pages of calendars are fetched."""
    freezer.move_to("2026-08-12T12:00:00Z")
    page = mock_calendar_api.get_calendars_endpoint.return_value
    page.total_pages = 2
    mock_calendar_api.get_calendars_endpoint.side_effect = [page, page]

    await setup_integration(hass, mock_config_entry)

    assert mock_calendar_api.get_calendars_endpoint.call_count == 2


async def test_cancelled_occurrence_is_hidden(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a cancelled occurrence is neither the next event nor listed."""
    # 13:00Z sits between the cancelled 14:00Z slot and the 16:00Z training,
    # so an unfiltered "next event" would be the cancelled one.
    freezer.move_to("2026-08-12T13:00:00Z")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["message"] == "Fotballtrening"

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            EVENT_START_DATETIME: "2026-08-12T00:00:00Z",
            EVENT_END_DATETIME: "2026-08-17T00:00:00Z",
        },
        blocking=True,
        return_response=True,
    )
    summaries = [event["summary"] for event in result[ENTITY_ID]["events"]]
    assert "Avlyst tannlegetime" not in summaries
