"""Tests for calendar platform of Holiday integration."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.holiday import calendar
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_async_get_events(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test events in a specific time frame."""
    freezer.move_to(datetime(2023, 1, 1, 12, tzinfo=dt_util.UTC))

    config_entry = MockConfigEntry(
        data={
            "country": "US",
            "province": "AK",
        }
    )
    entity = calendar.HolidayCalendarEntity(
        "United States, AK", "US", "AK", config_entry.entry_id
    )

    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 2)

    events = await entity.async_get_events(hass, start_date, end_date)

    # assert len(events) == 1
    assert events[0].summary == "New Year's Day"
    assert events[0].start == datetime(2023, 1, 1).date()
    assert events[0].end == datetime(2023, 1, 2).date()
    assert events[0].location == "United States, AK"
