"""Tests for the calendar automation.

The tests create calendar based automations, set up a fake set of calendar
events, then advance time to exercise that the automation is called. The
tests use a fixture that mocks out events returned by the calendar entity,
and create events using a relative time offset and then advance the clock
forward exercising the triggers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Generator
from contextlib import asynccontextmanager
import datetime
import logging
from typing import Any
from unittest.mock import patch
import zoneinfo

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import automation, calendar
from homeassistant.components.calendar.trigger import EVENT_END, EVENT_START
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import MockCalendarEntity

from tests.common import MockConfigEntry, async_fire_time_changed, async_mock_service

_LOGGER = logging.getLogger(__name__)


CALENDAR_ENTITY_ID = "calendar.calendar_2"

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

    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        """Initialize FakeSchedule."""
        self.hass = hass
        self.freezer = freezer

    async def fire_time(self, trigger_time: datetime.datetime) -> None:
        """Fire an alarm and wait."""
        _LOGGER.debug("Firing alarm @ %s", dt_util.as_local(trigger_time))
        self.freezer.move_to(trigger_time)
        async_fire_time_changed(self.hass, trigger_time)
        await self.hass.async_block_till_done()

    async def fire_until(self, end: datetime.datetime) -> None:
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
def fake_schedule(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> FakeSchedule:
    """Fixture that tests can use to make fake events."""

    # Setup start time for all tests
    freezer.move_to("2022-04-19 10:31:02+00:00")

    return FakeSchedule(hass, freezer)


@pytest.fixture(name="test_entity")
def mock_test_entity(test_entities: list[MockCalendarEntity]) -> MockCalendarEntity:
    """Fixture to expose the calendar entity used in tests."""
    return test_entities[1]


@pytest.fixture(name="setup_platform", autouse=True)
async def mock_setup_platform(
    hass: HomeAssistant,
    mock_setup_integration: None,
    config_entry: MockConfigEntry,
) -> None:
    """Fixture to setup platforms used in the test."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@asynccontextmanager
async def create_automation(
    hass: HomeAssistant, event_type: str, offset=None
) -> AsyncIterator[None]:
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
                "alias": event_type,
                "trigger": trigger_data,
                "action": TEST_AUTOMATION_ACTION,
                "mode": "queued",
            }
        },
    )
    await hass.async_block_till_done()

    yield

    # Disable automation to cleanup lingering timers
    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: f"automation.{event_type}"},
        blocking=True,
    )


@pytest.fixture
def calls_data(hass: HomeAssistant) -> Callable[[], list[dict[str, Any]]]:
    """Fixture to return payload data for automation calls."""
    service_calls = async_mock_service(hass, "test", "automation")

    def get_trigger_data() -> list[dict[str, Any]]:
        return [c.data for c in service_calls]

    return get_trigger_data


@pytest.fixture(autouse=True)
def mock_update_interval() -> Generator[None]:
    """Fixture to override the update interval for refreshing events."""
    with patch(
        "homeassistant.components.calendar.trigger.UPDATE_INTERVAL",
        new=TEST_UPDATE_INTERVAL,
    ):
        yield


async def test_event_start_trigger(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test the a calendar trigger based on start time."""
    event_data = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    async with create_automation(hass, EVENT_START):
        assert len(calls_data()) == 0

        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
        )

    assert calls_data() == [
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
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
    offset_str,
    offset_delta,
) -> None:
    """Test the a calendar trigger based on start time with an offset."""
    event_data = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 12:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 12:30:00+00:00"),
    )
    async with create_automation(hass, EVENT_START, offset=offset_str):
        # No calls yet
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:55:00+00:00") + offset_delta,
        )
        assert len(calls_data()) == 0

        # Event has started w/ offset
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 12:05:00+00:00") + offset_delta,
        )
        assert calls_data() == [
            {
                "platform": "calendar",
                "event": EVENT_START,
                "calendar_event": event_data,
            }
        ]


async def test_event_end_trigger(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test the a calendar trigger based on end time."""
    event_data = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 12:00:00+00:00"),
    )
    async with create_automation(hass, EVENT_END):
        # Event started, nothing should fire yet
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:10:00+00:00")
        )
        assert len(calls_data()) == 0

        # Event ends
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 12:10:00+00:00")
        )
        assert calls_data() == [
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
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
    offset_str,
    offset_delta,
) -> None:
    """Test the a calendar trigger based on end time with an offset."""
    event_data = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 12:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 12:30:00+00:00"),
    )
    async with create_automation(hass, EVENT_END, offset=offset_str):
        # No calls yet
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 12:05:00+00:00") + offset_delta,
        )
        assert len(calls_data()) == 0

        # Event has started w/ offset
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 12:35:00+00:00") + offset_delta,
        )
        assert calls_data() == [
            {
                "platform": "calendar",
                "event": EVENT_END,
                "calendar_event": event_data,
            }
        ]


async def test_calendar_trigger_with_no_events(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
) -> None:
    """Test a calendar trigger setup  with no events."""

    async with create_automation(hass, EVENT_START), create_automation(hass, EVENT_END):
        # No calls, at arbitrary times
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00")
        )
    assert len(calls_data()) == 0


async def test_multiple_start_events(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test that a trigger fires for multiple events."""

    event_data1 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 10:45:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
    )
    event_data2 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
    )
    async with create_automation(hass, EVENT_START):
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00")
        )
    assert calls_data() == [
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


async def test_multiple_end_events(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test that a trigger fires for multiple events."""

    event_data1 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 10:45:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
    )
    event_data2 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
    )
    async with create_automation(hass, EVENT_END):
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00")
        )

    assert calls_data() == [
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
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test that a trigger fires for every event sharing a start time."""

    event_data1 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    event_data2 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    async with create_automation(hass, EVENT_START):
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:35:00+00:00")
        )

    assert calls_data() == [
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


async def test_overlap_events(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test that a trigger fires for events that overlap."""

    event_data1 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    event_data2 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:45:00+00:00"),
    )
    async with create_automation(hass, EVENT_START):
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:20:00+00:00")
        )

    assert calls_data() == [
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


async def test_update_next_event(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test detection of a new event after initial trigger is setup."""

    event_data1 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
    )
    async with create_automation(hass, EVENT_START):
        # No calls before event start
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 10:45:00+00:00")
        )
        assert len(calls_data()) == 0

        # Create a new event between now and when the event fires
        event_data2 = test_entity.create_event(
            start=datetime.datetime.fromisoformat("2022-04-19 10:55:00+00:00"),
            end=datetime.datetime.fromisoformat("2022-04-19 11:05:00+00:00"),
        )

        # Advance past the end of the events
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00")
        )
    assert calls_data() == [
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


async def test_update_missed(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
) -> None:
    """Test that new events are missed if they arrive outside the update interval."""

    event_data1 = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    async with create_automation(hass, EVENT_START):
        # Events are refreshed at t+TEST_UPDATE_INTERVAL minutes. A new event is
        # added, but the next update happens after the event is already over.
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 10:38:00+00:00")
        )
        assert len(calls_data()) == 0

        test_entity.create_event(
            start=datetime.datetime.fromisoformat("2022-04-19 10:40:00+00:00"),
            end=datetime.datetime.fromisoformat("2022-04-19 10:55:00+00:00"),
        )

        # Only the first event is returned
        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:05:00+00:00")
        )
        assert calls_data() == [
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
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
    set_time_zone: None,
    create_data,
    fire_time,
    payload_data,
) -> None:
    """Test the fields in the calendar event payload are set."""
    test_entity.create_event(**create_data)
    async with create_automation(hass, EVENT_START):
        assert len(calls_data()) == 0

        await fake_schedule.fire_until(fire_time)
        assert calls_data() == [
            {
                "platform": "calendar",
                "event": EVENT_START,
                "calendar_event": payload_data,
            }
        ]


async def test_trigger_timestamp_window_edge(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that events in the edge of a scan are included."""
    freezer.move_to("2022-04-19 11:00:00+00:00")
    # Exactly at a TEST_UPDATE_INTERVAL boundary the start time,
    # making this excluded from the first window.
    event_data = test_entity.create_event(
        start=datetime.datetime.fromisoformat("2022-04-19 11:14:00+00:00"),
        end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
    )
    async with create_automation(hass, EVENT_START):
        assert len(calls_data()) == 0

        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:20:00+00:00")
        )
        assert calls_data() == [
            {
                "platform": "calendar",
                "event": EVENT_START,
                "calendar_event": event_data,
            }
        ]


async def test_event_start_trigger_dst(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entity: MockCalendarEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a calendar event trigger happening at the start of daylight savings time."""
    await hass.config.async_set_time_zone("America/Los_Angeles")
    tzinfo = zoneinfo.ZoneInfo("America/Los_Angeles")
    freezer.move_to("2023-03-12 01:00:00-08:00")

    # Before DST transition starts
    event1_data = test_entity.create_event(
        summary="Event 1",
        start=datetime.datetime(2023, 3, 12, 1, 30, tzinfo=tzinfo),
        end=datetime.datetime(2023, 3, 12, 1, 45, tzinfo=tzinfo),
    )
    # During DST transition (Clocks are turned forward at 2am to 3am)
    event2_data = test_entity.create_event(
        summary="Event 2",
        start=datetime.datetime(2023, 3, 12, 2, 30, tzinfo=tzinfo),
        end=datetime.datetime(2023, 3, 12, 2, 45, tzinfo=tzinfo),
    )
    # After DST transition has ended
    event3_data = test_entity.create_event(
        summary="Event 3",
        start=datetime.datetime(2023, 3, 12, 3, 30, tzinfo=tzinfo),
        end=datetime.datetime(2023, 3, 12, 3, 45, tzinfo=tzinfo),
    )
    async with create_automation(hass, EVENT_START):
        assert len(calls_data()) == 0

        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2023-03-12 05:00:00-08:00"),
        )

        assert calls_data() == [
            {
                "platform": "calendar",
                "event": EVENT_START,
                "calendar_event": event1_data,
            },
            {
                "platform": "calendar",
                "event": EVENT_START,
                "calendar_event": event2_data,
            },
            {
                "platform": "calendar",
                "event": EVENT_START,
                "calendar_event": event3_data,
            },
        ]


async def test_config_entry_reload(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entities: list[MockCalendarEntity],
    setup_platform: None,
    config_entry: MockConfigEntry,
) -> None:
    """Test the a calendar trigger after a config entry reload.

    This sets ups a config entry, sets up an automation for an entity in that
    config entry, then reloads the config entry. This reproduces a bug where
    the automation kept a reference to the specific entity which would be
    invalid after a config entry was reloaded.
    """
    async with create_automation(hass, EVENT_START):
        assert len(calls_data()) == 0

        assert await hass.config_entries.async_reload(config_entry.entry_id)

        # Ensure the reloaded entity has events upcoming.
        test_entity = test_entities[1]
        event_data = test_entity.create_event(
            start=datetime.datetime.fromisoformat("2022-04-19 11:00:00+00:00"),
            end=datetime.datetime.fromisoformat("2022-04-19 11:30:00+00:00"),
        )

        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
        )

    assert calls_data() == [
        {
            "platform": "calendar",
            "event": EVENT_START,
            "calendar_event": event_data,
        }
    ]


async def test_config_entry_unload(
    hass: HomeAssistant,
    calls_data: Callable[[], list[dict[str, Any]]],
    fake_schedule: FakeSchedule,
    test_entities: list[MockCalendarEntity],
    setup_platform: None,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an automation that references a calendar entity that is unloaded."""
    async with create_automation(hass, EVENT_START):
        assert len(calls_data()) == 0

        assert await hass.config_entries.async_unload(config_entry.entry_id)

        await fake_schedule.fire_until(
            datetime.datetime.fromisoformat("2022-04-19 11:15:00+00:00"),
        )

    assert "Entity does not exist calendar.calendar_2" in caplog.text
