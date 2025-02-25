"""Fixtures for Remote Calendar."""

from collections.abc import Awaitable, Callable, Generator
from http import HTTPStatus
import textwrap
from typing import Any
from unittest.mock import AsyncMock, patch
import urllib

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.remote_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator

CALENDAR_NAME = "Home Assistant Events"
TEST_ENTITY = "calendar.home_assistant_events"
CALENDER_URL = "https://calendar.google.com/calendar/ical/1a44d4f756085bb81ac3c681c96b6a9c84efda276593148fc3d9ade5289f557a%40group.calendar.google.com/public/basic.ics"
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
        DTSTART:19970714
        DTEND:19970715
        END:VEVENT
        END:VCALENDAR
        """
    )
    return request.param if hasattr(request, "param") else default_content


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


class Client:
    """Test client with helper methods for calendar websocket."""

    def __init__(self, client: ClientWebSocketResponse) -> None:
        """Initialize Client."""
        self.client = client
        self.id = 0

    async def cmd(
        self, cmd: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command and receive the json result."""
        self.id += 1
        await self.client.send_json(
            {
                "id": self.id,
                "type": f"calendar/event/{cmd}",
                **(payload if payload is not None else {}),
            }
        )
        resp = await self.client.receive_json()
        assert resp.get("id") == self.id
        return resp

    async def cmd_result(
        self, cmd: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Send a command and parse the result."""
        resp = await self.cmd(cmd, payload)
        assert resp.get("success")
        assert resp.get("type") == "result"
        return resp.get("result")


type ClientFixture = Callable[[], Awaitable[Client]]


@pytest.fixture
async def ws_client(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> ClientFixture:
    """Fixture for creating the test websocket client."""

    async def create_client() -> Client:
        ws_client = await hass_ws_client(hass)
        return Client(ws_client)

    return create_client
