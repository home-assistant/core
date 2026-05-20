"""Fixtures for School Holiday integration tests."""

from datetime import date
from unittest.mock import patch

import pytest

from homeassistant.components.school_holiday.const import (
    CONF_CALENDAR_NAME,
    CONF_SENSOR_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_COUNTRY, CONF_REGION

from tests.common import MockConfigEntry

TEST_ENTRY_ID = "550e8400e29b41d4a716446655440000"
TEST_SENSOR_NAME = "School Holiday Sensor"
TEST_COUNTRY = "nl"
TEST_REGION = "midden"
TEST_CALENDAR_NAME = "School Holiday Calendar"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id=TEST_ENTRY_ID,
        domain=DOMAIN,
        data={
            CONF_SENSOR_NAME: TEST_SENSOR_NAME,
            CONF_COUNTRY: TEST_COUNTRY,
            CONF_REGION: TEST_REGION,
            CONF_CALENDAR_NAME: TEST_CALENDAR_NAME,
        },
    )


@pytest.fixture
def mock_school_holiday_data() -> list[dict]:
    """Return mock school holiday data.

    Note: End dates use exclusive bounds (day after last holiday day).
    The coordinator adds 1 day to API end dates to make them inclusive.
    """
    return [
        {
            "summary": "Summer Holiday",
            "start": date(2026, 7, 18),
            "end": date(2026, 8, 31),  # Last day of holiday is 2026-08-30
            "description": None,
        },
        {
            "summary": "Autumn Holiday",
            "start": date(2026, 10, 17),
            "end": date(2026, 10, 26),  # Last day of holiday is 2026-10-25
            "description": "A week's holiday for school and college students in the autumn.",
        },
    ]


@pytest.fixture
def mock_api_response(mock_school_holiday_data):
    """Mock the API response for school holidays."""
    with patch(
        "homeassistant.components.school_holiday.coordinator.SchoolHolidayCoordinator._async_update_data"
    ) as mock_update:

        async def return_school_holidays():
            return mock_school_holiday_data

        mock_update.side_effect = return_school_holidays
        yield
