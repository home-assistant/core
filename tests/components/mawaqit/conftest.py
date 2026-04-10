"""Fixtures for the Mawaqit integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.mawaqit.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry

MOCK_UUID = "aaaaa-bbbbb-cccccc-0000"
MOCK_TOKEN = "test-api-token"
MOCK_LATITUDE = 48.8566
MOCK_LONGITUDE = 2.3522


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for Mawaqit."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="MAWAQIT - Test Mosque",
        data={
            CONF_API_KEY: MOCK_TOKEN,
            "uuid": MOCK_UUID,
            CONF_LATITUDE: MOCK_LATITUDE,
            CONF_LONGITUDE: MOCK_LONGITUDE,
        },
        unique_id="mawaqit_unique",
    )


@pytest.fixture
def mock_mosques() -> list[dict]:
    """Return mock mosque data."""
    return [
        {
            "uuid": "aaaaa-bbbbb-cccccc-0000",
            "name": "Mosque1",
            "type": "MOSQUE",
            "slug": "1-mosque",
            "latitude": 48,
            "longitude": 1,
            "jumua": None,
            "proximity": 1744,
            "label": "Mosque1-label",
            "localisation": "aaaaa bbbbb cccccc",
        },
        {
            "uuid": "bbbbb-cccccc-ddddd-0000",
            "name": "Mosque2",
            "type": "MOSQUE",
            "slug": "2-mosque",
            "latitude": 47,
            "longitude": 1,
            "jumua": None,
            "proximity": 20000,
            "label": "Mosque2-label",
            "localisation": "bbbbb cccccc ddddd",
        },
    ]


@pytest.fixture
def mock_prayer_data() -> dict:
    """Return mock prayer time data with calendar, timezone, etc."""
    # Build a 12-month calendar with prayer times for each day
    month_data = {}
    for day in range(1, 32):
        month_data[str(day)] = ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]

    calendar = [month_data.copy() for _ in range(12)]

    # Build iqama calendar (offsets like "+10", "+15")
    iqama_month_data = {}
    for day in range(1, 32):
        iqama_month_data[str(day)] = ["+10", "+15", "+10", "+5", "+10"]

    iqama_calendar = [iqama_month_data.copy() for _ in range(12)]

    return {
        "uuid": MOCK_UUID,
        "name": "Test Mosque",
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
        "shuruq": "06:45",
        "jumua": "13:00",
        "jumua2": "14:00",
        "announcements": [
            {"title": "Ramadan", "content": "Starts tomorrow"},
        ],
    }


@pytest.fixture
def mock_mosque_data() -> dict:
    """Return mock mosque detail data."""
    return {
        "uuid": MOCK_UUID,
        "name": "Test Mosque",
        "announcements": [
            {"title": "Ramadan", "content": "Starts tomorrow"},
        ],
    }


@pytest.fixture
def mock_mawaqit_client() -> Generator[MagicMock]:
    """Return a mocked AsyncMawaqitClient."""
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_api_token = AsyncMock(return_value=MOCK_TOKEN)
        client.all_mosques_neighborhood = AsyncMock(return_value=[])
        client.fetch_mosques_by_keyword = AsyncMock(return_value=[])
        client.fetch_prayer_times = AsyncMock(return_value={})
        client.fetch_mosque_by_id = AsyncMock(return_value={})
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.mawaqit.async_setup_entry", return_value=True):
        yield
