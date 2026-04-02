"""Tests for diagnostics platform of google calendar."""

from collections.abc import Callable
import time
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import TEST_EVENT, ApiResult, ComponentSetup

from tests.common import MockConfigEntry
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


@pytest.mark.freeze_time("2023-03-13 12:05:00-07:00")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    component_setup: ComponentSetup,
    mock_events_list_items: Callable[[list[dict[str, Any]]], None],
    config_entry: MockConfigEntry,
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

    data = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert data == snapshot
