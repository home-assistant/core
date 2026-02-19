"""Fixtures for School Holidays integration tests."""

import pytest

from homeassistant.components.school_holidays.utils import generate_unique_id
from homeassistant.const import CONF_COUNTRY, CONF_NAME, CONF_REGION

from tests.common import MockConfigEntry

DOMAIN = "school_holidays"

TEST_CALENDAR_NAME = "School Holidays"
TEST_COUNTRY = "The Netherlands"
TEST_REGION = "Midden"

TEST_SPRING_BREAK_DESCRIPTION = f"Spring Break for the region {TEST_REGION}."
TEST_SPRING_BREAK_END = "2026-02-22"
TEST_SPRING_BREAK_NAME = "Spring Break"
TEST_SPRING_BREAK_START = "2026-02-14"

TEST_SUMMER_HOLIDAY_DESCRIPTION = None
TEST_SUMMER_HOLIDAY_END = "2026-08-30"
TEST_SUMMER_HOLIDAY_NAME = "Summer Holiday"
TEST_SUMMER_HOLIDAY_START = "2026-07-18"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_CALENDAR_NAME,
        domain=DOMAIN,
        data={
            CONF_NAME: TEST_CALENDAR_NAME,
            CONF_COUNTRY: TEST_COUNTRY,
            CONF_REGION: TEST_REGION,
        },
        unique_id=generate_unique_id(TEST_COUNTRY, TEST_REGION),
    )
