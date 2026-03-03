"""Test coordinator for School Holiday integration."""

from datetime import date

import pytest

from homeassistant.components.school_holiday.coordinator import SchoolHolidayCoordinator
from homeassistant.core import HomeAssistant

from .conftest import TEST_COUNTRY, TEST_REGION

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.asyncio
async def test_coordinator_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test coordinator data update."""
    coordinator = SchoolHolidayCoordinator(
        hass, TEST_COUNTRY, TEST_REGION, mock_config_entry
    )

    # Mock the API response.
    aioclient_mock.get(
        "https://opendata.rijksoverheid.nl/v1/sources/rijksoverheid/infotypes/schoolholidays?output=json",
        json=[
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
        ],
    )

    data = await coordinator._async_update_data()

    assert len(data) == 1
    assert data[0]["summary"] == "Summer Holiday"
    assert data[0]["start"] == date(2026, 7, 18)
    # Add 1 day to the end date to make it inclusive, as done by the coordinator.
    assert data[0]["end"] == date(2026, 8, 31)


@pytest.mark.asyncio
async def test_coordinator_end_date_boundary(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the last day of a holiday is correctly treated as inclusive.

    The API returns exclusive end dates, but the coordinator adds 1 day
    to make them inclusive, ensuring the last holiday day is included.
    """
    coordinator = SchoolHolidayCoordinator(
        hass, TEST_COUNTRY, TEST_REGION, mock_config_entry
    )

    # Mock API response with end date 2026-10-25.
    aioclient_mock.get(
        "https://opendata.rijksoverheid.nl/v1/sources/rijksoverheid/infotypes/schoolholidays?output=json",
        json=[
            {
                "content": [
                    {
                        "vacations": [
                            {
                                "type": "Autumn Holiday",
                                "regions": [
                                    {
                                        "region": TEST_REGION,
                                        "startdate": "2026-10-17",
                                        "enddate": "2026-10-25",
                                    }
                                ],
                                "compulsorydates": True,
                            }
                        ]
                    }
                ],
                "notice": None,
            }
        ],
    )

    data = await coordinator._async_update_data()

    assert len(data) == 1
    # Verify the coordinator transforms exclusive end date to inclusive.
    assert data[0]["start"] == date(2026, 10, 17)
    assert data[0]["end"] == date(2026, 10, 26)  # API: 2026-10-25 + 1 day

    # Verify boundary: 2026-10-25 (the API end date) should be within the holiday period.
    last_holiday_day = date(2026, 10, 25)
    assert data[0]["start"] <= last_holiday_day < data[0]["end"]
