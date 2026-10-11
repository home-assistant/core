"""Tests for calendar triggers on CalDAV calendars."""

import datetime
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from caldav.calendarobjectresource import Event
from caldav.lib.url import URL
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.caldav.coordinator import CalDavUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service

TEST_ENTITY = "calendar.example"

CALDAV_CONFIG = {
    "platform": "caldav",
    "url": "http://test.local",
    "custom_calendars": [],
}

ALL_DAY_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
BEGIN:VEVENT
UID:all-day
DTSTAMP:20171125T000000Z
DTSTART;VALUE=DATE:20171128
DTEND;VALUE=DATE:20171129
SUMMARY:All day event
END:VEVENT
END:VCALENDAR
"""


def _as_utc(value: datetime.date | datetime.datetime) -> datetime.datetime:
    """Interpret a DATE or floating DATE-TIME in UTC, like a CalDAV server."""
    if not isinstance(value, datetime.datetime):
        return datetime.datetime.combine(value, datetime.time.min, tzinfo=dt_util.UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_util.UTC)
    return value


def _mock_calendar(ics_events: list[str]) -> Mock:
    """Return a mock calendar that filters searches by time range like a server."""
    calendar = Mock()
    calendar.client = None
    calendar.url = URL("http://test.local/calendar/")
    calendar.get_display_name = MagicMock(return_value="Example")
    calendar.get_supported_components = MagicMock(return_value=["VEVENT"])
    events = [
        Event(None, f"{idx}.ics", ics, calendar, str(idx))
        for idx, ics in enumerate(ics_events)
    ]

    def _search(
        start: datetime.datetime, end: datetime.datetime, **kwargs: Any
    ) -> list[Event]:
        result = []
        for event in events:
            vevent = event.vobject_instance.vevent
            event_start = _as_utc(vevent.dtstart.value)
            event_end = _as_utc(CalDavUpdateCoordinator.get_end_date(vevent))
            if event_start < end and event_end > start:
                result.append(event)
        return result

    calendar.search = MagicMock(side_effect=_search)
    return calendar


@pytest.mark.parametrize("tz", ["UTC", "Europe/Berlin", "America/New_York"])
@pytest.mark.parametrize("trigger_event", ["start", "end"])
async def test_all_day_event_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tz: str,
    trigger_event: str,
) -> None:
    """Test the calendar trigger fires for an all-day event in any time zone.

    The event starts and ends at local midnight, which a server matching dates
    in UTC places a few hours off (issue #154204).
    """
    await hass.config.async_set_time_zone(tz)
    trigger_day = (
        datetime.date(2017, 11, 28)
        if trigger_event == "start"
        else datetime.date(2017, 11, 29)
    )
    trigger_time = datetime.datetime.combine(
        trigger_day, datetime.time.min, tzinfo=dt_util.get_default_time_zone()
    )
    freezer.move_to(trigger_time - datetime.timedelta(minutes=20))

    with patch("homeassistant.components.caldav.calendar.DAVClient") as mock_client:
        mock_client.return_value.get_principal.return_value.get_calendars.return_value = [
            _mock_calendar([ALL_DAY_EVENT])
        ]
        assert await async_setup_component(
            hass, "calendar", {"calendar": CALDAV_CONFIG}
        )
        await hass.async_block_till_done()

    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": {
                    "trigger": "calendar",
                    "event": trigger_event,
                    "entity_id": TEST_ENTITY,
                },
                "actions": {
                    "action": "test.automation",
                    "data": {"summary": "{{ trigger.calendar_event.summary }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    # Advance minute by minute so every scheduled refresh and alarm runs
    while dt_util.now() < trigger_time + datetime.timedelta(minutes=20):
        freezer.tick(datetime.timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["summary"] == "All day event"
