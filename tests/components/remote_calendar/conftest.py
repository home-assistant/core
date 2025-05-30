"""Fixtures for Remote Calendar."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
import textwrap
from typing import Any
import urllib

import pytest

from homeassistant.components.remote_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

CALENDAR_NAME = "Home Assistant Events"
TEST_ENTITY = "calendar.home_assistant_events"
CALENDER_URL = "https://some.calendar.com/calendar.ics"
FRIENDLY_NAME = "Home Assistant Events"


@pytest.fixture(name="time_zone")
def mock_time_zone() -> str:
    """Fixture for time zone to use in tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    return "America/Regina"


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant, time_zone: str):
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    await hass.config.async_set_time_zone(time_zone)


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_CALENDAR_NAME: CALENDAR_NAME, CONF_URL: CALENDER_URL}
    )


type GetEventsFn = Callable[[str, str], Awaitable[list[dict[str, Any]]]]


@pytest.fixture(name="get_events")
def get_events_fixture(hass_client: ClientSessionGenerator) -> GetEventsFn:
    """Fetch calendar events from the HTTP API."""

    async def _fetch(start: str, end: str) -> list[dict[str, Any]]:
        client = await hass_client()
        response = await client.get(
            f"/api/calendars/{TEST_ENTITY}?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}"
        )
        assert response.status == HTTPStatus.OK
        return await response.json()

    return _fetch


def event_fields(data: dict[str, str]) -> dict[str, str]:
    """Filter event API response to minimum fields."""
    return {
        k: data[k]
        for k in ("summary", "start", "end", "recurrence_id", "location")
        if data.get(k)
    }


@pytest.fixture(name="ics_content")
def mock_ics_content(request: pytest.FixtureRequest) -> str:
    """Fixture to allow tests to set initial ics content for the calendar store."""
    default_content = textwrap.dedent(
        """\
        BEGIN:VCALENDAR
        BEGIN:VEVENT
        SUMMARY:Bastille Day Party
        DTSTART:19970714T170000Z
        DTEND:19970715T040000Z
        END:VEVENT
        END:VCALENDAR
        """
    )
    return request.param if hasattr(request, "param") else default_content
