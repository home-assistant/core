"""Test __init__.py for School Holiday integration."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.school_holiday.coordinator import SchoolHolidayCoordinator
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_COUNTRY,
    TEST_REGION,
    TEST_SUMMER_HOLIDAY_END,
    TEST_SUMMER_HOLIDAY_NAME,
    TEST_SUMMER_HOLIDAY_START,
)

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_coordinator_update_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator data update."""
    coordinator = SchoolHolidayCoordinator(
        hass, TEST_COUNTRY, TEST_REGION, mock_config_entry
    )

    class MockResponse:
        def __init__(self) -> None:
            self.status = 200

        async def json(self):
            return [
                {
                    "content": [
                        {
                            "vacations": [
                                {
                                    "type": TEST_SUMMER_HOLIDAY_NAME,
                                    "regions": [
                                        {
                                            "region": TEST_REGION,
                                            "startdate": TEST_SUMMER_HOLIDAY_START,
                                            "enddate": TEST_SUMMER_HOLIDAY_END,
                                        }
                                    ],
                                    "compulsorydates": True,
                                }
                            ]
                        }
                    ],
                    "notice": None,
                }
            ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class MockSession:
        def get(self, _url, timeout=None):
            return MockResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    with patch(
        "homeassistant.components.school_holiday.coordinator.aiohttp.ClientSession",
        return_value=MockSession(),
    ):
        data = await coordinator._async_update_data()

        assert len(data) == 1
        assert data[0]["summary"] == TEST_SUMMER_HOLIDAY_NAME
        assert data[0]["start"].isoformat() == TEST_SUMMER_HOLIDAY_START
        # Add 1 day to the end date to make it inclusive, as done in the coordinator.
        end = date.fromisoformat(TEST_SUMMER_HOLIDAY_END) + timedelta(days=1)
        assert data[0]["end"] == end


@pytest.mark.asyncio
async def test_coordinator_invalid_country(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator with invalid country."""
    coordinator = SchoolHolidayCoordinator(
        hass, "Invalid Country", "Region", mock_config_entry
    )

    data = await coordinator._async_update_data()

    assert data == []
