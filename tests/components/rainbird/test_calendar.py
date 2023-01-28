"""Tests for rainbird calendar platform."""


from collections.abc import Awaitable, Callable
import datetime
from http import HTTPStatus
from typing import Any
import urllib
from zoneinfo import ZoneInfo

from aiohttp import ClientSession
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup, mock_response

from tests.test_util.aiohttp import AiohttpClientMockResponse

TEST_ENTITY = "calendar.rain_bird_controller"
GetEventsFn = Callable[[str, str], Awaitable[dict[str, Any]]]

MODEL_VERSION_RESPONSE = "820005090C"
SCHEDULE_RESPONSES = [
    # Current controller status
    "A0000000000000",
    # Per-program information
    "A00010060602006400",  # CUSTOM: Monday & Tuesday
    "A00011110602006400",
    "A00012000300006400",
    # Start times per program
    "A0006000F0FFFFFFFFFFFF",  # 4am
    "A00061FFFFFFFFFFFFFFFF",
    "A00062FFFFFFFFFFFFFFFF",
    # Run times for each zone
    "A00080001900000000001400000000",  # zone1=25, zone2=20
    "A00081000700000000001400000000",  # zone3=7, zone4=20
    "A00082000A00000000000000000000",  # zone5=10
    "A00083000000000000000000000000",
    "A00084000000000000000000000000",
    "A00085000000000000000000000000",
    "A00086000000000000000000000000",
    "A00087000000000000000000000000",
    "A00088000000000000000000000000",
    "A00089000000000000000000000000",
    "A0008A000000000000000000000000",
]


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.CALENDAR]


@pytest.fixture(autouse=True)
def set_time_zone(hass: HomeAssistant):
    """Set the time zone for the tests."""
    hass.config.set_time_zone("America/Regina")


@pytest.fixture(autouse=True)
def mock_schedule_responses(responses: list[AiohttpClientMockResponse]) -> list[str]:
    """Mock response to return the irrigation schedule."""
    # Example schedule from TM2
    responses.extend(
        [
            mock_response(api_response)
            for api_response in [MODEL_VERSION_RESPONSE] + SCHEDULE_RESPONSES
        ]
    )


@pytest.fixture(name="get_events")
def get_events_fixture(
    hass_client: Callable[..., Awaitable[ClientSession]]
) -> GetEventsFn:
    """Fetch calendar events from the HTTP API."""

    async def _fetch(start: str, end: str) -> list[dict[str, Any]]:
        client = await hass_client()
        response = await client.get(
            f"/api/calendars/{TEST_ENTITY}?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}"
        )
        assert response.status == HTTPStatus.OK
        results = await response.json()
        return [{k: event[k] for k in {"summary", "start", "end"}} for event in results]

    return _fetch


@freeze_time("2023-01-21 09:32:00")
async def test_get_events(
    hass: HomeAssistant, setup_integration: ComponentSetup, get_events: GetEventsFn
) -> None:
    """Test calendar event fetching APIs."""

    assert await setup_integration()

    events = await get_events("2023-01-20T00:00:00Z", "2023-02-05T00:00:00Z")
    assert events == [
        # Monday
        {
            "summary": "PGM A",
            "start": {"dateTime": "2023-01-23T04:00:00-06:00"},
            "end": {"dateTime": "2023-01-23T05:22:00-06:00"},
        },
        # Tuesday
        {
            "summary": "PGM A",
            "start": {"dateTime": "2023-01-24T04:00:00-06:00"},
            "end": {"dateTime": "2023-01-24T05:22:00-06:00"},
        },
        # Monday
        {
            "summary": "PGM A",
            "start": {"dateTime": "2023-01-30T04:00:00-06:00"},
            "end": {"dateTime": "2023-01-30T05:22:00-06:00"},
        },
        # Tuesday
        {
            "summary": "PGM A",
            "start": {"dateTime": "2023-01-31T04:00:00-06:00"},
            "end": {"dateTime": "2023-01-31T05:22:00-06:00"},
        },
    ]


@pytest.mark.parametrize(
    "freeze_time,expected_state",
    [
        (
            datetime.datetime(2023, 1, 23, 3, 50, tzinfo=ZoneInfo("America/Regina")),
            "off",
        ),
        (
            datetime.datetime(2023, 1, 23, 4, 30, tzinfo=ZoneInfo("America/Regina")),
            "on",
        ),
    ],
)
async def test_event_state(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    get_events: GetEventsFn,
    freezer: FrozenDateTimeFactory,
    freeze_time: datetime.datetime,
    expected_state: str,
) -> None:
    """Test calendar upcoming event state."""
    freezer.move_to(freeze_time)

    assert await setup_integration()

    state = hass.states.get(TEST_ENTITY)
    assert state is not None
    assert state.attributes == {
        "message": "PGM A",
        "start_time": "2023-01-23 04:00:00",
        "end_time": "2023-01-23 05:22:00",
        "all_day": False,
        "description": "",
        "location": "",
        "friendly_name": "Rain Bird Controller",
        "icon": "mdi:sprinkler",
    }
    assert state.state == expected_state
