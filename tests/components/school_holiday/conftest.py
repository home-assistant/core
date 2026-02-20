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

TEST_SENSOR_NAME = "School Holiday Sensor"
TEST_CALENDAR_NAME = "School Holiday Calendar"

TEST_COUNTRY = "The Netherlands"
TEST_REGION = "Midden"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_SENSOR_NAME,
        domain=DOMAIN,
        data={
            CONF_SENSOR_NAME: TEST_SENSOR_NAME,
            CONF_CALENDAR_NAME: TEST_CALENDAR_NAME,
            CONF_COUNTRY: TEST_COUNTRY,
            CONF_REGION: TEST_REGION,
        },
    )


@pytest.fixture
def mock_school_holiday_data() -> list[dict]:
    """Return mock school holiday data."""
    return [
        {
            "summary": "Spring Break",
            "start": date(2026, 2, 14),
            "end": date(2026, 2, 22),
            "description": "A week's holiday for school and college students in March or April.",
        },
        {
            "summary": "Summer Holiday",
            "start": date(2026, 7, 18),
            "end": date(2026, 8, 30),
            "description": None,
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
