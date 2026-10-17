"""The tests for the group calendar platform."""

import datetime as dt

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.components.group import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockPlatform, async_fire_time_changed, mock_platform

GROUP_ENTITY_ID = "calendar.family"
NOW = dt.datetime(2026, 10, 17, 12, 0, tzinfo=dt.UTC)

WORK_ATTRIBUTES = {
    "message": "Meeting",
    "all_day": False,
    "start_time": "2026-10-17 11:00:00",
    "end_time": "2026-10-17 13:00:00",
    "location": "Office",
    "description": "",
}
HOME_ATTRIBUTES = {
    "message": "Dinner",
    "all_day": False,
    "start_time": "2026-10-17 18:00:00",
    "end_time": "2026-10-17 20:00:00",
    "location": "",
    "description": "With friends",
}


class MockCalendarEntity(CalendarEntity):
    """Calendar entity serving a fixed list of events."""

    def __init__(self, name: str, events: list[CalendarEvent]) -> None:
        """Initialize the calendar."""
        self._attr_name = name
        self._events = events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._events[0] if self._events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: dt.datetime,
        end_date: dt.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            event
            for event in self._events
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Use UTC to keep member state attributes readable."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to(NOW)


async def _setup_group(hass: HomeAssistant, extra_config: list[ConfigType]) -> None:
    """Set up a calendar group of calendar.work and calendar.home."""
    await async_setup_component(
        hass,
        CALENDAR_DOMAIN,
        {
            CALENDAR_DOMAIN: [
                *extra_config,
                {
                    "platform": DOMAIN,
                    "entities": ["calendar.work", "calendar.home"],
                    "name": "Family",
                    "unique_id": "unique_identifier",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def test_state(hass: HomeAssistant) -> None:
    """Test calendar group state follows the earliest member event."""
    await _setup_group(hass, [])

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set("calendar.work", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes == {
        ATTR_ENTITY_ID: ["calendar.work", "calendar.home"],
        "friendly_name": "Family",
    }

    hass.states.async_set("calendar.home", STATE_OFF, HOME_ATTRIBUTES)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Dinner"
    assert state.attributes["description"] == "With friends"

    hass.states.async_set("calendar.work", STATE_ON, WORK_ATTRIBUTES)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes == {
        ATTR_ENTITY_ID: ["calendar.work", "calendar.home"],
        "friendly_name": "Family",
        "message": "Meeting",
        "all_day": False,
        "start_time": "2026-10-17 11:00:00",
        "end_time": "2026-10-17 13:00:00",
        "location": "Office",
        "description": "",
    }

    hass.states.async_set("calendar.work", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Dinner"

    hass.states.async_set("calendar.home", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_all_day_event(hass: HomeAssistant) -> None:
    """Test an all day member event is preferred when it started earlier."""
    await _setup_group(hass, [])

    hass.states.async_set("calendar.work", STATE_ON, WORK_ATTRIBUTES)
    hass.states.async_set(
        "calendar.home",
        STATE_ON,
        {
            "message": "Holiday",
            "all_day": True,
            "start_time": "2026-10-17 00:00:00",
            "end_time": "2026-10-18 00:00:00",
            "location": "",
            "description": "",
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Holiday"
    assert state.attributes["all_day"] is True
    assert state.attributes["start_time"] == "2026-10-17 00:00:00"
    assert state.attributes["end_time"] == "2026-10-18 00:00:00"


async def test_event_ends(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test the group moves to the next event when the current one ends."""
    await _setup_group(hass, [])

    hass.states.async_set("calendar.work", STATE_ON, WORK_ATTRIBUTES)
    hass.states.async_set("calendar.home", STATE_OFF, HOME_ATTRIBUTES)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Meeting"

    freezer.move_to(NOW + dt.timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Dinner"


async def test_get_events(hass: HomeAssistant) -> None:
    """Test the group returns the events of all members."""
    entities = [
        MockCalendarEntity(
            "Work",
            [
                CalendarEvent(
                    start=NOW - dt.timedelta(hours=1),
                    end=NOW + dt.timedelta(hours=1),
                    summary="Meeting",
                    location="Office",
                ),
            ],
        ),
        MockCalendarEntity(
            "Home",
            [
                CalendarEvent(
                    start=NOW.date(),
                    end=NOW.date() + dt.timedelta(days=1),
                    summary="Holiday",
                ),
                CalendarEvent(
                    start=NOW + dt.timedelta(hours=6),
                    end=NOW + dt.timedelta(hours=8),
                    summary="Dinner",
                    description="With friends",
                ),
            ],
        ),
    ]

    async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        async_add_entities(entities)

    mock_platform(
        hass,
        f"test.{CALENDAR_DOMAIN}",
        MockPlatform(async_setup_platform=async_setup_platform),
    )
    await _setup_group(hass, [{"platform": "test"}])

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Holiday"

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: GROUP_ENTITY_ID,
            "start_date_time": dt_util.start_of_local_day(),
            "duration": {"days": 1},
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        GROUP_ENTITY_ID: {
            "events": [
                {
                    "start": "2026-10-17",
                    "end": "2026-10-18",
                    "summary": "Holiday",
                },
                {
                    "start": "2026-10-17T11:00:00+00:00",
                    "end": "2026-10-17T13:00:00+00:00",
                    "summary": "Meeting",
                    "location": "Office",
                },
                {
                    "start": "2026-10-17T18:00:00+00:00",
                    "end": "2026-10-17T20:00:00+00:00",
                    "summary": "Dinner",
                    "description": "With friends",
                },
            ]
        }
    }
