"""Fixtures for the Skylight integration tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.calendar import CalendarEvent
from homeassistant.components.skylight.const import (
    CONF_DEVICE_FINGERPRINT,
    CONF_FRAME_ID,
    CONF_FRAME_NAME,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.components.skylight.coordinator import SkylightData

from tests.common import MockConfigEntry

FRAME_ID = "frame-1"
FRAME_NAME = "Home Frame"
FRAME = {"id": FRAME_ID, "name": FRAME_NAME}

TOKEN = {
    CONF_ACCESS_TOKEN: "mock-access-token",
    CONF_REFRESH_TOKEN: "mock-refresh-token",
    CONF_DEVICE_FINGERPRINT: "mock-fingerprint",
}

ENTRY_DATA = {
    CONF_FRAME_ID: FRAME_ID,
    CONF_FRAME_NAME: FRAME_NAME,
    CONF_TOKEN: TOKEN,
}

EVENT_START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
EVENT_END = datetime(2026, 10, 10, 10, 0, tzinfo=UTC)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Patch the setup entry of the Skylight integration."""
    with patch(
        f"homeassistant.components.{DOMAIN}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_get_frames() -> Generator[AsyncMock]:
    """Mock skylight_api.SkylightAPI.get_frames to return a single frame."""
    with patch(
        "skylight_api.SkylightAPI.get_frames",
        return_value=[FRAME],
    ) as mock_get_frames:
        yield mock_get_frames


@pytest.fixture
def mock_get_frames_two() -> Generator[AsyncMock]:
    """Mock skylight_api.SkylightAPI.get_frames to return two frames."""
    with patch(
        "skylight_api.SkylightAPI.get_frames",
        return_value=[FRAME, {"id": "frame-2", "name": "Cottage Frame"}],
    ) as mock_get_frames:
        yield mock_get_frames


@pytest.fixture
def mock_exchange_token() -> Generator[AsyncMock]:
    """Mock the OAuth authorization-code exchange."""
    with patch(
        "homeassistant.components.skylight.config_flow.exchange_authorization_code",
        return_value={
            CONF_ACCESS_TOKEN: TOKEN[CONF_ACCESS_TOKEN],
            CONF_REFRESH_TOKEN: TOKEN[CONF_REFRESH_TOKEN],
        },
    ) as mock_exchange:
        yield mock_exchange


@pytest.fixture
def mock_coordinator_data() -> Generator[AsyncMock]:
    """Make the coordinator return one upcoming event without hitting the API."""

    data = SkylightData(
        events=[
            CalendarEvent(
                start=EVENT_START,
                end=EVENT_END,
                summary="Family dinner",
                description="At grandma's",
                uid="event-1",
            )
        ]
    )
    with patch(
        "homeassistant.components.skylight.coordinator."
        "SkylightDataUpdateCoordinator._async_update_data",
        new_callable=AsyncMock,
        return_value=data,
    ) as mock_update:
        yield mock_update


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a ready-to-set-up config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=FRAME_NAME,
        unique_id=f"skylight_frame_{FRAME_ID}",
        data=ENTRY_DATA,
    )
