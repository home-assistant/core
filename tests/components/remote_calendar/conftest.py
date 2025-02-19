"""Fixtures for Remote Calendar."""

from collections.abc import Awaitable, Callable, Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch
import urllib

import pytest

from homeassistant.components.remote_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

CALENDAR_NAME = "Home Assistant Events"
TEST_ENTITY = "calendar.home_assistant_events"
CALENDER_URL = "https://calendar.google.com/calendar/ical/1a44d4f756085bb81ac3c681c96b6a9c84efda276593148fc3d9ade5289f557a%40group.calendar.google.com/public/basic.ics"


@pytest.fixture(name="ics_content")
def mock_ics_content() -> str:
    """Fixture to allow tests to set initial ics content for the calendar store."""
    return """BEGIN:VCALENDAR
                VERSION:2.0
                PRODID:-//hacksw/handcal//NONSGML v1.0//EN
                END:VCALENDAR
            """


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


@pytest.fixture
def mock_httpx_client(ics_content) -> Generator[AsyncMock]:
    """Mock an httpx client."""
    client = AsyncMock()
    response = AsyncMock()
    response.status_code = 200
    response.text = ics_content

    response.raise_for_status = lambda: None
    client.get.return_value = response

    with (
        patch(
            "homeassistant.components.remote_calendar.coordinator.get_async_client",
            return_value=client,
        ),
        patch(
            "homeassistant.components.remote_calendar.config_flow.get_async_client",
            return_value=client,
        ),
    ):
        yield client
