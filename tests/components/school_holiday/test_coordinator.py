"""Test __init__.py for School Holiday integration."""

from datetime import date
from unittest.mock import patch

import pytest

from homeassistant.components.school_holiday.coordinator import SchoolHolidayCoordinator
from homeassistant.core import HomeAssistant

from .conftest import TEST_COUNTRY, TEST_REGION

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
                                    "type": "Summer Holiday",
                                    "regions": [
                                        {
                                            "region": TEST_REGION,
                                            "startdate": "2026-07-18",
                                            "enddate": "2026-08-30",
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

        def close(self):
            pass

    with patch(
        "homeassistant.components.school_holiday.coordinator.aiohttp.ClientSession",
        return_value=MockSession(),
    ):
        data = await coordinator._async_update_data()

        assert len(data) == 1
        assert data[0]["summary"] == "Summer Holiday"
        assert data[0]["start"] == date(2026, 7, 18)
        # Add 1 day to the end date to make it inclusive, as done by the coordinator.
        assert data[0]["end"] == date(2026, 8, 31)
