"""Tests for rainbird calendar platform."""

from collections.abc import Awaitable, Callable
import datetime
from http import HTTPStatus
from typing import Any
import urllib
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import CONFIG_ENTRY_DATA_OLD_FORMAT, mock_response, mock_response_error

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMockResponse
from tests.typing import ClientSessionGenerator

TEST_ENTITY = "calendar.rain_bird_controller"
type GetEventsFn = Callable[[str, str], Awaitable[dict[str, Any]]]

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

EMPTY_SCHEDULE_RESPONSES = [
    # Current controller status
    "A0000000000000",
    # Per-program information (ignored)
    "A00010000000000000",
    "A00011000000000000",
    "A00012000000000000",
    # Start times for each program (off)
    "A00060FFFFFFFFFFFFFFFF",
    "A00061FFFFFFFFFFFFFFFF",
    "A00062FFFFFFFFFFFFFFFF",
    # Run times for each zone
    "A00080000000000000000000000000",
    "A00081000000000000000000000000",
    "A00082000000000000000000000000",
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
async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[Platform]:
    """Fixture to setup the config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant):
    """Set the time zone for the tests."""
    await hass.config.async_set_time_zone("America/Regina")


@pytest.fixture(autouse=True)
def mock_schedule_responses() -> list[str]:
    """Fixture containing fake irrigation schedule."""
    return SCHEDULE_RESPONSES


@pytest.fixture(autouse=True)
def mock_insert_schedule_response(
    mock_schedule_responses: list[str], responses: list[AiohttpClientMockResponse]
) -> None:
    """Fixture to insert device responses for the irrigation schedule."""
    responses.extend(
        [mock_response(api_response) for api_response in mock_schedule_responses]
    )


@pytest.fixture(name="get_events")
def get_events_fixture(
    hass_client: ClientSessionGenerator,
) -> GetEventsFn:
    """Fetch calendar events from the HTTP API."""

    async def _fetch(start: str, end: str) -> list[dict[str, Any]]:
        client = await hass_client()
        response = await client.get(
            f"/api/calendars/{TEST_ENTITY}?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}"
        )
        assert response.status == HTTPStatus.OK
        results = await response.json()
        return [{k: event[k] for k in ("summary", "start", "end")} for event in results]

    return _fetch


@pytest.mark.freeze_time("2023-01-21 09:32:00")
async def test_get_events(hass: HomeAssistant, get_events: GetEventsFn) -> None:
    """Test calendar event fetching APIs."""

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
    ("freeze_time", "expected_state", "setup_config_entry"),
    [
        (
            datetime.datetime(2023, 1, 23, 3, 50, tzinfo=ZoneInfo("America/Regina")),
            "off",
            None,
        ),
        (
            datetime.datetime(2023, 1, 23, 4, 30, tzinfo=ZoneInfo("America/Regina")),
            "on",
            None,
        ),
    ],
)
async def test_event_state(
    hass: HomeAssistant,
    get_events: GetEventsFn,
    freezer: FrozenDateTimeFactory,
    freeze_time: datetime.datetime,
    expected_state: str,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test calendar upcoming event state."""
    freezer.move_to(freeze_time)

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

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
    }
    assert state.state == expected_state

    entity = entity_registry.async_get(TEST_ENTITY)
    assert entity
    assert entity.unique_id == "4c:a1:61:00:11:22"


@pytest.mark.parametrize(
    ("model_and_version_response", "has_entity"),
    [
        ("820005090C", True),
        ("820006090C", False),
    ],
    ids=("ESP-TM2", "ST8x-WiFi"),
)
async def test_calendar_not_supported_by_device(
    hass: HomeAssistant,
    has_entity: bool,
) -> None:
    """Test calendar upcoming event state."""

    state = hass.states.get(TEST_ENTITY)
    assert (state is not None) == has_entity


@pytest.mark.parametrize(
    "mock_insert_schedule_response",
    [([None])],  # Disable success responses
)
async def test_no_schedule(
    hass: HomeAssistant,
    get_events: GetEventsFn,
    responses: list[AiohttpClientMockResponse],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test calendar error when fetching the calendar."""
    responses.extend([mock_response_error(HTTPStatus.BAD_GATEWAY)])  # Arbitrary error

    state = hass.states.get(TEST_ENTITY)
    assert state.state == "unavailable"
    assert state.attributes == {
        "friendly_name": "Rain Bird Controller",
    }

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{TEST_ENTITY}?start=2023-08-01&end=2023-08-02"
    )
    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.freeze_time("2023-01-21 09:32:00")
@pytest.mark.parametrize(
    "mock_schedule_responses",
    [(EMPTY_SCHEDULE_RESPONSES)],
)
async def test_program_schedule_disabled(
    hass: HomeAssistant,
    get_events: GetEventsFn,
) -> None:
    """Test calendar when the program is disabled with no upcoming events."""

    events = await get_events("2023-01-20T00:00:00Z", "2023-02-05T00:00:00Z")
    assert events == []

    state = hass.states.get(TEST_ENTITY)
    assert state.state == "off"
    assert state.attributes == {
        "friendly_name": "Rain Bird Controller",
    }


@pytest.mark.parametrize(
    ("config_entry_data", "config_entry_unique_id", "setup_config_entry"),
    [
        (CONFIG_ENTRY_DATA_OLD_FORMAT, None, None),
    ],
)
async def test_no_unique_id(
    hass: HomeAssistant,
    get_events: GetEventsFn,
    responses: list[AiohttpClientMockResponse],
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test calendar entity with no unique id."""

    # Failure to migrate config entry to a unique id
    responses.insert(0, mock_response_error(HTTPStatus.SERVICE_UNAVAILABLE))

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY)
    assert state is not None
    assert state.attributes.get("friendly_name") == "Rain Bird Controller"

    entity_entry = entity_registry.async_get(TEST_ENTITY)
    assert not entity_entry
