"""Fixtures for local calendar."""

from collections.abc import Awaitable, Callable, Generator
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import patch
import urllib

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.auth.models import Credentials
from homeassistant.components.local_calendar import LocalCalendarStore
from homeassistant.components.local_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import CLIENT_ID, MockConfigEntry, MockUser
from tests.typing import ClientSessionGenerator, WebSocketGenerator

CALENDAR_NAME = "Light Schedule"
FRIENDLY_NAME = "Light schedule"
TEST_ENTITY = "calendar.light_schedule"


class FakeStore(LocalCalendarStore):
    """Mock storage implementation."""

    def __init__(self, hass: HomeAssistant, path: Path, ics_content: str) -> None:
        """Initialize FakeStore."""
        super().__init__(hass, path)
        self._content = ics_content

    def _load(self) -> str:
        """Read from calendar storage."""
        return self._content

    def _store(self, ics_content: str) -> None:
        """Persist the calendar storage."""
        self._content = ics_content


@pytest.fixture(name="ics_content", autouse=True)
def mock_ics_content() -> str:
    """Fixture to allow tests to set initial ics content for the calendar store."""
    return ""


@pytest.fixture(name="store", autouse=True)
def mock_store(ics_content: str) -> Generator[None, None, None]:
    """Test cleanup, remove any media storage persisted during the test."""

    stores: dict[Path, FakeStore] = {}

    def new_store(hass: HomeAssistant, path: Path) -> FakeStore:
        if path not in stores:
            stores[path] = FakeStore(hass, path, ics_content)
        return stores[path]

    with patch(
        "homeassistant.components.local_calendar.LocalCalendarStore", new=new_store
    ):
        yield


@pytest.fixture(name="time_zone")
def mock_time_zone() -> str:
    """Fixture for time zone to use in tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    return "America/Regina"


@pytest.fixture(autouse=True)
def set_time_zone(hass: HomeAssistant, time_zone: str):
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    hass.config.set_time_zone(time_zone)


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_CALENDAR_NAME: CALENDAR_NAME})


async def _setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture(name="setup_integration")
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration."""
    await _setup_integration(hass, config_entry)


@pytest.fixture(name="setup_integration_func")
async def setup_integration_func(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Callable[[], Awaitable[None]]:
    """Fixture that will set up the integration."""

    async def _func():
        await _setup_integration(hass, config_entry)

    return _func


GetEventsFn = Callable[[str, str], Awaitable[list[dict[str, Any]]]]


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
        for k in ["summary", "start", "end", "recurrence_id", "location"]
        if data.get(k)
    }


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


async def generate_new_hass_access_token(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
) -> str:
    """Return an access token to access Home Assistant."""
    await hass.auth.async_link_user(hass_admin_user, hass_admin_credential)

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )
    return hass.auth.async_create_access_token(refresh_token)


ClientFixture = Callable[[], Awaitable[Client]]


@pytest.fixture
async def ws_client(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
    hass_ws_client: WebSocketGenerator,
) -> ClientFixture:
    """Fixture for creating the test websocket client."""

    async def create_client() -> Client:
        access_token = await generate_new_hass_access_token(
            hass, hass_admin_user, hass_admin_credential
        )
        ws_client = await hass_ws_client(hass, access_token=access_token)
        return Client(ws_client)

    return create_client
