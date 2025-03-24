"""Tests for diagnostics platform of google calendar."""

from collections.abc import Callable
import time
from typing import Any

from aiohttp.test_utils import TestClient
from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.auth.models import Credentials
from homeassistant.core import HomeAssistant

from .conftest import TEST_EVENT, ApiResult, ComponentSetup

from tests.common import CLIENT_ID, MockConfigEntry, MockUser
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def mock_test_setup(
    test_api_calendar: dict[str, Any],
    mock_calendars_list: ApiResult,
) -> None:
    """Fixture that sets up the default API responses during integration setup."""
    mock_calendars_list({"items": [test_api_calendar]})


async def generate_new_hass_access_token(
    hass: HomeAssistant, hass_admin_user: MockUser, hass_admin_credential: Credentials
) -> str:
    """Return an access token to access Home Assistant."""
    await hass.auth.async_link_user(hass_admin_user, hass_admin_credential)

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )
    return hass.auth.async_create_access_token(refresh_token)


def _get_test_client_generator(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator, new_token: str
):
    """Return a test client generator.""."""

    async def auth_client() -> TestClient:
        return await aiohttp_client(
            hass.http.app, headers={"Authorization": f"Bearer {new_token}"}
        )

    return auth_client


@freeze_time("2023-03-13 12:05:00-07:00")
@pytest.mark.usefixtures("socket_enabled")
async def test_diagnostics(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_events_list_items: Callable[[list[dict[str, Any]]], None],
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
    config_entry: MockConfigEntry,
    aiohttp_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test diagnostics for the calendar."""

    expires_in = 86400
    expires_at = time.time() + expires_in
    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        json={
            "refresh_token": "some-refresh-token",
            "access_token": "some-updated-token",
            "expires_at": expires_at,
            "expires_in": expires_in,
        },
    )
    mock_events_list_items(
        [
            {
                **TEST_EVENT,
                "id": "event-id-1",
                "iCalUID": "event-id-1@google.com",
                "start": {"dateTime": "2023-03-13 12:00:00-07:00"},
                "end": {"dateTime": "2023-03-13 12:30:00-07:00"},
            },
            {
                **TEST_EVENT,
                "id": "event-id-2",
                "iCalUID": "event-id-2@google.com",
                "summary": "All Day Event",
                "start": {"date": "2022-10-08"},
                "end": {"date": "2022-10-09"},
                "recurrence": ["RRULE:FREQ=WEEKLY"],
            },
        ]
    )

    assert await component_setup()

    # Since we are freezing time only when we enter this test, we need to
    # manually create a new token and clients since the token created by
    # the fixtures would not be valid.
    new_token = await generate_new_hass_access_token(
        hass, hass_admin_user, hass_admin_credential
    )
    data = await get_diagnostics_for_config_entry(
        hass, _get_test_client_generator(hass, aiohttp_client, new_token), config_entry
    )
    assert data == snapshot
