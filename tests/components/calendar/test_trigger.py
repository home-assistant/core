"""Tests for the calendar automation.

The tests create calendar based automations, set up a fake set of calendar
events, then advance time to exercise that the automation is called. The
tests use a fixture that mocks out events returned by the calendar entity,
and create events using a relative time offset and then advance the clock
forward exercising the triggers.
"""
from __future__ import annotations

from collections.abc import Callable, Generator
import datetime
import logging
import secrets
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import calendar
import homeassistant.components.automation as automation
from homeassistant.components.calendar.trigger import EVENT_END, EVENT_START
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service

_LOGGER = logging.getLogger(__name__)


CALENDAR_ENTITY_ID = "calendar.calendar_2"
CONFIG = {calendar.DOMAIN: {"platform": "demo"}}

TEST_AUTOMATION_ACTION = {
    "service": "test.automation",
    "data": {
        "platform": "{{ trigger.platform }}",
        "event": "{{ trigger.event }}",
        "calendar_event": "{{ trigger.calendar_event }}",
    },
}

# The trigger sets two alarms: One based on the next event and one
# to refresh the schedule. The test advances the time an arbitrary
# amount to trigger either type of event with a small jitter.
TEST_TIME_ADVANCE_INTERVAL = datetime.timedelta(minutes=1)
TEST_UPDATE_INTERVAL = datetime.timedelta(minutes=7)


class FakeSchedule:
    """Test fixture class for return events in a specific date range."""

    def __init__(self, hass, freezer):
        """Initiailize FakeSchedule."""
        self.hass = hass
        self.freezer = freezer
        # Map of event start time to event
        self.events: list[calendar.CalendarEvent] = []

    def create_event(
        self,
        start: datetime.timedelta,
        end: datetime.timedelta,
        summary: str | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """Create a new fake event, used by tests."""
        event = calendar.CalendarEvent(
            start=start,
            end=end,
            summary=summary if summary else f"Event {secrets.token_hex(16)}",
            description=description,
            location=location,
        )
        self.events.append(event)
        return event.as_dict()

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[calendar.CalendarEvent]:
        """Get all events in a specific time frame, used by the demo calendar."""
        assert start_date < end_date
        values = []
        local_start_date = dt_util.as_local(start_date)
        local_end_date = dt_util.as_local(end_date)
        for event in self.events:
            if (
                event.start_datetime_local < local_end_date
                and local_start_date < event.end_datetime_local
            ):
                values.append(event)
        return values

    async def fire_time(self, trigger_time: datetime.datetime) -> None:
        """Fire an alarm and wait."""
        _LOGGER.debug(f"Firing alarm @ {trigger_time}")
        self.freezer.move_to(trigger_time)
        async_fire_time_changed(self.hass, trigger_time)
        await self.hass.async_block_till_done()

    async def fire_until(self, end: datetime.timedelta) -> None:
        """Simulate the passage of time by firing alarms until the time is reached."""

        current_time = dt_util.as_utc(self.freezer())
        if (end - current_time) > (TEST_UPDATE_INTERVAL * 2):
            # Jump ahead to right before the target alarm them to remove
            # unnecessary waiting, before advancing in smaller increments below.
            # This leaves time for multiple update intervals to refresh the set
            # of upcoming events
            await self.fire_time(end - TEST_UPDATE_INTERVAL * 2)

        while dt_util.utcnow() < end:
            self.freezer.tick(TEST_TIME_ADVANCE_INTERVAL)
            await self.fire_time(dt_util.utcnow())


@pytest.fixture
def set_time_zone(hass):
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    hass.config.set_time_zone("America/Regina")


@pytest.fixture
def fake_schedule(hass, freezer):
    """Fixture that tests can use to make fake events."""

    # Setup start time for all tests
    freezer.move_to("2022-04-19 10:31:02+00:00")

    schedule = FakeSchedule(hass, freezer)
    with patch(
        "homeassistant.components.demo.calendar.DemoCalendar.async_get_events",
        new=schedule.async_get_events,
    ):
        yield schedule


@pytest.fixture(autouse=True)
async def setup_calendar(hass: HomeAssistant, fake_schedule: FakeSchedule) -> None:
    """Initialize the demo calendar."""
    assert await async_setup_component(hass, calendar.DOMAIN, CONFIG)
    await hass.async_block_till_done()


async def create_automation(hass: HomeAssistant, event_type: str, offset=None) -> None:
    """Register an automation."""
    trigger_data = {
        "platform": calendar.DOMAIN,
        "entity_id": CALENDAR_ENTITY_ID,
        "event": event_type,
    }
    if offset:
        trigger_data["offset"] = offset
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": trigger_data,
                "action": TEST_AUTOMATION_ACTION,
                "mode": "queued",
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
def calls(hass: HomeAssistant) -> Callable[[], list]:
    """Fixture to return payload data for automation calls."""
    service_calls = async_mock_service(hass, "test", "automation")

    def get_trigger_data() -> list:
        return [c.data for c in service_calls]

    return get_trigger_data


@pytest.fixture(autouse=True)
def mock_update_interval() -> Generator[None, None, None]:
    """Fixture to override the update interval for refreshing events."""
    with patch(
        "homeassistant.components.calendar.trigger.UPDATE_INTERVAL",
        new=TEST_UPDATE_INTERVAL,
    ):
        yield


async def test_event_start_trigger(hass: HomeAssistant, calls, fake_schedule) -> None:
    """Test the a calendar trigger based on start time."""
    event_data = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    await create_automation(hass, EVENT_START)
    assert len(calls()) == 0

    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data,
        }
    ]


@pytest.mark.parametrize(
    ("offset_str", "offset_delta"),
    [
        ("-01:00", datetime.timedelta(hours=-1)),
        ("+01:00", datetime.timedelta(hours=1)),
    ],
)
async def test_event_start_trigger_with_offset(
    hass: HomeAssistant, calls, fake_schedule, offset_str, offset_delta
) -> None:
    """Test the a calendar trigger based on start time with an offset."""
    event_data = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 12:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 12:30:00+00:00"),
    )
    await create_automation(hass, EVENT_START, offset=offset_str)

    # No calls yet
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:55:00+00:00") + offset_delta,
    )
    assert len(calls()) == 0

    # Event has started w/ offset
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 12:05:00+00:00") + offset_delta,
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data,
        }
    ]


async def test_event_end_trigger(hass: HomeAssistant, calls, fake_schedule) -> None:
    """Test the a calendar trigger based on end time."""
    event_data = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 12:00:00+00:00"),
    )
    await create_automation(hass, EVENT_END)

    # Event started, nothing should fire yet
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:10:00+00:00")
    )
    assert len(calls()) == 0

    # Event ends
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 12:10:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_END,
            "calendar_event": event_data,
        }
    ]


@pytest.mark.parametrize(
    ("offset_str", "offset_delta"),
    [
        ("-01:00", datetime.timedelta(hours=-1)),
        ("+01:00", datetime.timedelta(hours=1)),
    ],
)
async def test_event_end_trigger_with_offset(
    hass: HomeAssistant, calls, fake_schedule, offset_str, offset_delta
) -> None:
    """Test the a calendar trigger based on end time with an offset."""
    event_data = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 12:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 12:30:00+00:00"),
    )
    await create_automation(hass, EVENT_END, offset=offset_str)

    # No calls yet
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 12:05:00+00:00") + offset_delta,
    )
    assert len(calls()) == 0

    # Event has started w/ offset
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 12:35:00+00:00") + offset_delta,
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_END,
            "calendar_event": event_data,
        }
    ]


async def test_calendar_trigger_with_no_events(
    hass: HomeAssistant, calls, fake_schedule
) -> None:
    """Test a calendar trigger setup  with no events."""

    await create_automation(hass, EVENT_START)
    await create_automation(hass, EVENT_END)

    # No calls, at arbitrary times
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00")
    )
    assert len(calls()) == 0


async def test_multiple_start_events(hass: HomeAssistant, calls, fake_schedule) -> None:
    """Test that a trigger fires for multiple events."""

    event_data1 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 10:45:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
    )
    event_data2 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
    )
    await create_automation(hass, EVENT_START)

    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data1,
        },
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data2,
        },
    ]


async def test_multiple_end_events(hass: HomeAssistant, calls, fake_schedule) -> None:
    """Test that a trigger fires for multiple events."""

    event_data1 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 10:45:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
    )
    event_data2 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
    )
    await create_automation(hass, EVENT_END)

    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_END,
            "calendar_event": event_data1,
        },
        {
            "platform": "calendar",
            "event": EVENT_END,
            "calendar_event": event_data2,
        },
    ]


async def test_multiple_events_sharing_start_time(
    hass: HomeAssistant, calls, fake_schedule
) -> None:
    """Test that a trigger fires for every event sharing a start time."""

    event_data1 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    event_data2 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    await create_automation(hass, EVENT_START)

    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:35:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data1,
        },
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data2,
        },
    ]


async def test_overlap_events(hass: HomeAssistant, calls, fake_schedule) -> None:
    """Test that a trigger fires for events that overlap."""

    event_data1 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    event_data2 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:45:00+00:00"),
    )
    await create_automation(hass, EVENT_START)

    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:20:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data1,
        },
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data2,
        },
    ]


async def test_invalid_calendar_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test creating a trigger with an invalid calendar id."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "action": TEST_AUTOMATION_ACTION,
                "trigger": {
                    "platform": calendar.DOMAIN,
                    "entity_id": "invalid-calendar-id",
                },
            }
        },
    )
    await hass.async_block_till_done()
    assert "Entity ID invalid-calendar-id is an invalid entity ID" in caplog.text


async def test_legacy_entity_type(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test creating a trigger with an invalid calendar id."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "action": TEST_AUTOMATION_ACTION,
                "trigger": {
                    "platform": calendar.DOMAIN,
                    "entity_id": "calendar.calendar_3",
                },
            }
        },
    )
    await hass.async_block_till_done()
    assert "is not a calendar entity" in caplog.text


async def test_update_next_event(hass: HomeAssistant, calls, fake_schedule) -> None:
    """Test detection of a new event after initial trigger is setup."""

    event_data1 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
    )
    await create_automation(hass, EVENT_START)

    # No calls before event start
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 10:45:00+00:00")
    )
    assert len(calls()) == 0

    # Create a new event between now and when the event fires
    event_data2 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 10:55:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:05:00+00:00"),
    )

    # Advance past the end of the events
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data2,
        },
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data1,
        },
    ]


async def test_update_missed(hass: HomeAssistant, calls, fake_schedule) -> None:
    """Test that new events are missed if they arrive outside the update interval."""

    event_data1 = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    await create_automation(hass, EVENT_START)

    # Events are refreshed at t+TEST_UPDATE_INTERVAL minutes. A new event is
    # added, but the next update happens after the event is already over.
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 10:38:00+00:00")
    )
    assert len(calls()) == 0

    fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 10:40:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 10:55:00+00:00"),
    )

    # Only the first event is returned
    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:05:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data1,
        },
    ]


@pytest.mark.parametrize(
    ("create_data", "fire_time", "payload_data"),
    [
        (
            {
                "start": datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
                "end": datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
                "summary": "Summary",
            },
            datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
            {
                "summary": "Summary",
                "start": "2022-04-19T11:00:00+00:00",
                "end": "2022-04-19T11:30:00+00:00",
                "all_day": False,
            },
        ),
        (
            {
                "start": datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
                "end": datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
                "summary": "Summary",
                "description": "Description",
                "location": "Location",
            },
            datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
            {
                "summary": "Summary",
                "start": "2022-04-19T11:00:00+00:00",
                "end": "2022-04-19T11:30:00+00:00",
                "all_day": False,
                "description": "Description",
                "location": "Location",
            },
        ),
        (
            {
                "summary": "Summary",
                "start": datetime.date.fromisoformat("2022-04-20"),
                "end": datetime.date.fromisoformat("2022-04-21"),
            },
            datetime.datetime.fromisoformat("2022-04-20 00:00:01-06:00"),
            {
                "summary": "Summary",
                "start": "2022-04-20",
                "end": "2022-04-21",
                "all_day": True,
            },
        ),
    ],
    ids=["basic", "more-fields", "all-day"],
)
async def test_event_payload(
    hass: HomeAssistant,
    calls,
    fake_schedule,
    set_time_zone,
    create_data,
    fire_time,
    payload_data,
) -> None:
    """Test the fields in the calendar event payload are set."""
    fake_schedule.create_event(**create_data)
    await create_automation(hass, EVENT_START)
    assert len(calls()) == 0

    await fake_schedule.fire_until(fire_time)
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": payload_data,
        }
    ]


async def test_trigger_timestamp_window_edge(
    hass: HomeAssistant, calls, fake_schedule, freezer
) -> None:
    """Test that events in the edge of a scan are included."""
    freezer.move_to("2022-04-19 11:00:00+00:00")
    # Exactly at a TEST_UPDATE_INTERVAL boundary the start time,
    # making this excluded from the first window.
    event_data = fake_schedule.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:14:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    await create_automation(hass, EVENT_START)
    assert len(calls()) == 0

    await fake_schedule.fire_until(
        datetime.datetime.fromisoformat("2022-04-19 11:20:00+00:00")
    )
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data,
        }
    ]
