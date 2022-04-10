"""Tests for the calendar automation.

The tests create calendar based automations, set up a fake set of calendar
events, then advance time to exercise that the automation is called. The
tests use a fixture that mocks out events returned by the calendar entity,
and create events using a relative time offset and then advance the clock
forward exercising the triggers.
"""
from __future__ import annotations

from collections.abc import Callable
import datetime
import logging
import secrets
from typing import Any, Generator
from unittest.mock import patch

import pytest

from homeassistant.components import calendar
import homeassistant.components.automation as automation
from homeassistant.components.calendar.trigger import EVENT_START
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service

_LOGGER = logging.getLogger(__name__)


CALENDAR_ENTITY_ID = "calendar.calendar_2"
CONFIG = {calendar.DOMAIN: {"platform": "demo"}}

TEST_AUTOMATION_ACTION = {
    "service": "test.automation",
    "data_template": {
        "platform": "{{ trigger.platform }}",
        "event": "{{ trigger.event }}",
        "calendar_event": "{{ trigger.calendar_event }}",
    },
}

# The trigger sets two alarms: One based on the next event and one
# to refresh the schedule. The test advances the time an arbitrary
# amount to trigger either type of event with a small jitter.
TEST_TIME_ADVANCE_INTERVAL = datetime.timedelta(minutes=1)
TEST_UPDATE_INTERVAL = datetime.timedelta(minutes=15)


@pytest.fixture
async def now() -> datetime.datetime:
    """Fixture to provide a base time for tests."""
    return dt_util.utcnow()


class FakeSchedule:
    """Test fixture class for return events in a specific date range."""

    def __init__(self, now: datetime.datetime) -> None:
        """Initiailize FakeSchedule."""
        # Map of event start time to event
        self.events: list[calendar.CalendarEvent] = []
        self.now = now

    def create_event(
        self, start_timedelta: datetime.timedelta, end_timedelta: datetime.timedelta
    ) -> dict[str, Any]:
        """Create a new fake event, used by tests."""
        event = calendar.CalendarEvent(
            start=(self.now + start_timedelta),
            end=(self.now + end_timedelta),
            summary=f"Event {secrets.token_hex(16)}",  # Arbitrary unique data
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
        for event in self.events:
            if (
                start_date < event.start_datetime_local < end_date
                or start_date < event.end_datetime_local < end_date
            ):
                values.append(event)
        return values


@pytest.fixture
def fake_schedule(now: datetime.datetime) -> Generator[FakeSchedule, None, None]:
    """Fixture that tests can use to make fake events."""
    schedule = FakeSchedule(now)
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


async def create_automation(
    hass: HomeAssistant, event_type: str, offset: str | None = None
) -> None:
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


async def fire_time(hass: HomeAssistant, trigger_time: datetime.datetime) -> None:
    """Fire an alarm and wait."""
    _LOGGER.debug(f"Firing alarm @ {trigger_time}")
    with patch("homeassistant.util.dt.utcnow", return_value=trigger_time):
        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()


async def fire_between(
    hass: HomeAssistant,
    now: datetime.datetime,
    end_delta: datetime.timedelta,
) -> datetime.datetime:
    """Simulate the passage of time by firing alarms until the time is reached."""
    trigger_time = now
    while trigger_time < (now + end_delta):
        trigger_time = trigger_time + TEST_TIME_ADVANCE_INTERVAL
        await fire_time(hass, trigger_time)
    return trigger_time


async def test_event_start_trigger(hass, calls, fake_schedule, now):
    """Test the a calendar trigger based on start time."""
    event_data = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=30),
        end_timedelta=datetime.timedelta(minutes=60),
    )
    await create_automation(hass, EVENT_START)
    assert len(calls()) == 0

    await fire_between(hass, now, datetime.timedelta(hours=1, minutes=5))
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data,
        }
    ]


async def test_calendar_trigger_with_no_events(hass, calls, fake_schedule, now):
    """Test a calendar trigger setup  with no events."""

    await create_automation(hass, EVENT_START)

    # No calls, at arbitrary times
    await fire_between(hass, now, datetime.timedelta(minutes=30))
    assert len(calls()) == 0


async def test_multiple_events(hass, calls, fake_schedule, now):
    """Test that a trigger fires for multiple events."""

    event_data1 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=15),
        end_timedelta=datetime.timedelta(minutes=30),
    )
    event_data2 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=45),
        end_timedelta=datetime.timedelta(minutes=60),
    )
    await create_automation(hass, EVENT_START)

    await fire_between(hass, now, datetime.timedelta(minutes=75))
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


async def test_multiple_events_sharing_start_time(hass, calls, fake_schedule, now):
    """Test that a trigger fires for every event sharing a start time."""

    event_data1 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=30),
        end_timedelta=datetime.timedelta(minutes=60),
    )
    event_data2 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=30),
        end_timedelta=datetime.timedelta(minutes=60),
    )
    await create_automation(hass, EVENT_START)

    await fire_between(hass, now, datetime.timedelta(minutes=75))
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


async def test_overlap_events(hass, calls, fake_schedule, now):
    """Test that a trigger fires for events that overlap."""

    event_data1 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=15),
        end_timedelta=datetime.timedelta(minutes=45),
    )
    event_data2 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=30),
        end_timedelta=datetime.timedelta(minutes=60),
    )
    await create_automation(hass, EVENT_START)

    await fire_between(hass, now, datetime.timedelta(minutes=75))
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


async def test_invalid_calendar_id(hass, caplog):
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
    assert "Invalid config for [automation]" in caplog.text


async def test_update_next_event(hass, calls, fake_schedule, now):
    """Test detection of a new event after initial trigger is setup."""

    event_data1 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=45),
        end_timedelta=datetime.timedelta(minutes=60),
    )
    await create_automation(hass, EVENT_START)

    # No calls before event start
    current_time = await fire_between(hass, now, datetime.timedelta(minutes=10))
    assert len(calls()) == 0

    # Create a new event between now and when the event fires
    event_data2 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=30),
        end_timedelta=datetime.timedelta(minutes=40),
    )

    # Advance past the end of the events
    await fire_between(hass, current_time, datetime.timedelta(minutes=60))
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


async def test_update_missed(hass, calls, fake_schedule, now):
    """Test that new events are missed if they arrive outside the update interval."""

    event_data1 = fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=45),
        end_timedelta=datetime.timedelta(minutes=60),
    )
    await create_automation(hass, EVENT_START)

    # Events are refreshed at t+15 minutes. A new event is added, but the next
    # update happens after the event is already over.
    current_time = await fire_between(hass, now, datetime.timedelta(minutes=20))
    assert len(calls()) == 0

    fake_schedule.create_event(
        start_timedelta=datetime.timedelta(minutes=30),
        end_timedelta=datetime.timedelta(minutes=40),
    )

    # Only the first event is returned
    await fire_between(hass, current_time, datetime.timedelta(minutes=60))
    assert calls() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data1,
        },
    ]
